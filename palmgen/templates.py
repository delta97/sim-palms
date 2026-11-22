"""Template loader and renderer (Jinja2 under strict rules).

A template set is a directory holding ``templates.yaml`` and the ``*.xml.j2`` files it lists.
Templates may use only ``{{ name }}``, ``{{ a.b }}``, ``{{ guid("role") }}`` and
``{% for x in name %}...{% endfor %}``. There are no filters, conditionals or arithmetic: the
writer pre-formats every value, and a missing value is an error, never an empty string.
Both rules are checked when the set is loaded, so a bad template never reaches a build.

Whether any element or attribute name in a real template is correct is not decided here:
the real templates come from SPIKE-003 captures (GEN-009).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import jinja2
import yaml
from lxml import etree

from palmgen import ids
from palmgen.errors import GenerationError

SCHEMA_VERSION: Final = 1
TEMPLATES_YAML: Final = "templates.yaml"

_GUID_STYLES: Final = ("braces_upper", "braces_lower", "plain_upper", "plain_lower")
_VERTEX_ORDERS: Final = ("ccw", "cw")
_LINE_ENDINGS: Final = {"lf": "\n", "crlf": "\r\n"}
_MAX_DECIMALS: Final = 15

_NAME = r"[a-z_][a-z0-9_]*"
_COMMENT_RE: Final = re.compile(r"\{#.*?#\}", re.DOTALL)
_TAG_RE: Final = re.compile(r"\{%-?(.*?)-?%\}", re.DOTALL)
_EXPR_RE: Final = re.compile(r"\{\{-?(.*?)-?\}\}", re.DOTALL)
_FOR_RE: Final = re.compile(rf"\s*for\s+{_NAME}\s+in\s+{_NAME}\s*")
_ENDFOR_RE: Final = re.compile(r"\s*endfor\s*")
_VALUE_RE: Final = re.compile(rf"\s*{_NAME}(\.{_NAME})*\s*")
_GUID_CALL_RE: Final = re.compile(r"""\s*guid\(\s*(["'])[A-Za-z0-9_.-]+\1\s*\)\s*""")


@dataclass(frozen=True)
class FormatSpec:
    """The ``format`` block of ``templates.yaml``."""

    guid_style: str
    lat_decimals: int
    lon_decimals: int
    heading_decimals: int
    scale_decimals: int
    vertex_order: str
    ring_closed: bool
    supports_holes: bool
    line_ending: str
    scene_dir: str

    @property
    def newline(self) -> Literal["\n", "\r\n"]:
        """The line-ending sequence named by ``line_ending``."""
        return "\r\n" if self.line_ending == "crlf" else "\n"


@dataclass(frozen=True)
class _Entry:
    file: str
    count_xpath: str | None


def _fail(msg: str) -> GenerationError:
    return GenerationError(msg)


def _parse_format(raw: Any, where: str) -> FormatSpec:
    if not isinstance(raw, Mapping):
        raise _fail(f"{where}: 'format' must be a mapping")
    int_keys = ("lat_decimals", "lon_decimals", "heading_decimals", "scale_decimals")
    bool_keys = ("ring_closed", "supports_holes")
    str_keys = ("guid_style", "vertex_order", "line_ending", "scene_dir")
    wanted = set(int_keys) | set(bool_keys) | set(str_keys)
    missing = sorted(wanted - set(raw))
    unknown = sorted(set(raw) - wanted)
    if missing:
        raise _fail(f"{where}: 'format' is missing keys: {', '.join(missing)}")
    if unknown:
        raise _fail(f"{where}: 'format' has unknown keys: {', '.join(unknown)}")
    for key in int_keys:
        v = raw[key]
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= _MAX_DECIMALS:
            raise _fail(f"{where}: format.{key} must be an integer 0..{_MAX_DECIMALS}, got {v!r}")
    for key in bool_keys:
        if not isinstance(raw[key], bool):
            raise _fail(f"{where}: format.{key} must be true or false, got {raw[key]!r}")
    for key in str_keys:
        if not isinstance(raw[key], str):
            raise _fail(f"{where}: format.{key} must be a string, got {raw[key]!r}")
    if raw["guid_style"] not in _GUID_STYLES:
        raise _fail(f"{where}: format.guid_style must be one of {', '.join(_GUID_STYLES)}")
    if raw["vertex_order"] not in _VERTEX_ORDERS:
        raise _fail(f"{where}: format.vertex_order must be one of {', '.join(_VERTEX_ORDERS)}")
    if raw["line_ending"] not in _LINE_ENDINGS:
        raise _fail(f"{where}: format.line_ending must be one of {', '.join(_LINE_ENDINGS)}")
    return FormatSpec(**{k: raw[k] for k in sorted(wanted)})


def _parse_entries(raw: Any, where: str) -> dict[str, _Entry]:
    if not isinstance(raw, Mapping) or not raw:
        raise _fail(f"{where}: 'templates' must be a non-empty mapping")
    entries: dict[str, _Entry] = {}
    for name, body in raw.items():
        if not isinstance(name, str) or not re.fullmatch(_NAME, name):
            raise _fail(f"{where}: template name {name!r} must be lower snake case")
        if not isinstance(body, Mapping) or not isinstance(body.get("file"), str):
            raise _fail(f"{where}: template {name!r} needs a 'file' string")
        extra = sorted(set(body) - {"file", "count_xpath"})
        if extra:
            raise _fail(f"{where}: template {name!r} has unknown keys: {', '.join(extra)}")
        xpath = body.get("count_xpath")
        if xpath is not None:
            if not isinstance(xpath, str) or not xpath.strip():
                raise _fail(f"{where}: template {name!r} count_xpath must be a non-empty string")
            try:
                etree.XPath(xpath)
            except etree.XPathSyntaxError as exc:
                raise _fail(f"{where}: template {name!r} count_xpath is invalid: {exc}") from exc
        entries[name] = _Entry(file=body["file"], count_xpath=xpath)
    return entries


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_template_source(source: str, name: str) -> None:
    """Reject any construct outside the allowed set; the error names the template and line.

    Allowed: ``{{ name }}``, ``{{ a.b }}``, ``{{ guid("role") }}``, ``{% for x in name %}``,
    ``{% endfor %}`` and ``{# comments #}``. Whitespace-control dashes are accepted.
    """
    # Blank out comments but keep their newlines, so reported line numbers stay right.
    text = _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), source)
    for m in _TAG_RE.finditer(text):
        body = m.group(1)
        where = f"template {name!r} line {_line_of(text, m.start())}"
        if "|" in body:
            raise _fail(f"{where}: filters are not allowed")
        if not (_FOR_RE.fullmatch(body) or _ENDFOR_RE.fullmatch(body)):
            raise _fail(
                f"{where}: only 'for' and 'endfor' tags are allowed, got {{% {body.strip()} %}}"
            )
    for m in _EXPR_RE.finditer(text):
        body = m.group(1)
        where = f"template {name!r} line {_line_of(text, m.start())}"
        if "|" in body:
            raise _fail(f"{where}: filters are not allowed")
        if not (_VALUE_RE.fullmatch(body) or _GUID_CALL_RE.fullmatch(body)):
            raise _fail(
                f"{where}: only a placeholder name or guid(role) may appear in "
                f"double braces, got {body.strip()!r}"
            )
    leftover = _EXPR_RE.sub("", _TAG_RE.sub("", text))
    for opener in ("{%", "{{", "{#"):
        pos = leftover.find(opener)
        if pos >= 0:
            raise _fail(
                f"template {name!r}: unterminated {opener!r} near {leftover[pos : pos + 20]!r}"
            )


class TemplateSet:
    """A loaded, validated set of templates plus the number format from ``templates.yaml``."""

    def __init__(
        self,
        directory: Path,
        fmt: FormatSpec,
        entries: dict[str, _Entry],
        env: jinja2.Environment,
        placeholder_model: dict[str, Any] | None,
        captured: dict[str, Any] | None,
    ) -> None:
        self.directory = directory
        self.format = fmt
        self.placeholder_model = placeholder_model
        self.captured = captured
        self._entries = entries
        self._compiled = {name: env.get_template(e.file) for name, e in entries.items()}

    @classmethod
    def load(cls, directory: Path) -> TemplateSet:
        """Load ``directory/templates.yaml`` and every template it lists."""
        directory = Path(directory)
        yaml_path = directory / TEMPLATES_YAML
        where = str(yaml_path)
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise _fail(f"{where}: not found") from exc
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            raise _fail(f"{where}: cannot read: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise _fail(f"{where}: top level must be a mapping")
        version = raw.get("schema_version")
        if isinstance(version, bool) or version != SCHEMA_VERSION:
            raise _fail(f"{where}: schema_version must be {SCHEMA_VERSION}")
        fmt = _parse_format(raw.get("format"), where)
        entries = _parse_entries(raw.get("templates"), where)
        placeholder_model = raw.get("placeholder_model")
        if placeholder_model is not None and not isinstance(placeholder_model, Mapping):
            raise _fail(f"{where}: placeholder_model must be a mapping or absent")
        captured = raw.get("captured")
        if captured is not None and not isinstance(captured, Mapping):
            raise _fail(f"{where}: captured must be a mapping or absent")

        root = directory.resolve()
        for name, entry in entries.items():
            path = (directory / entry.file).resolve()
            if not path.is_relative_to(root):
                raise _fail(f"template {name!r}: file {entry.file!r} is outside {directory}")
            if not path.is_file():
                raise _fail(f"template {name!r}: file {entry.file!r} does not exist in {directory}")
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise _fail(f"template {name!r}: cannot read {entry.file!r}: {exc}") from exc
            if source.startswith("﻿"):
                raise _fail(
                    f"template {name!r}: {entry.file!r} starts with a BOM; use UTF-8 without"
                )
            check_template_source(source, name)

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(directory), encoding="utf-8"),
            undefined=jinja2.StrictUndefined,
            autoescape=True,
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
            newline_sequence=fmt.newline,
        )
        try:
            return cls(
                directory,
                fmt,
                entries,
                env,
                dict(placeholder_model) if placeholder_model is not None else None,
                dict(captured) if captured is not None else None,
            )
        except jinja2.TemplateSyntaxError as exc:
            raise _fail(f"template {exc.name!r} line {exc.lineno}: {exc.message}") from exc

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def count_xpath(self, name: str) -> str | None:
        """The ``count_xpath`` of a template, or ``None`` when it has none."""
        try:
            return self._entries[name].count_xpath
        except KeyError:
            raise _fail(f"unknown template {name!r}") from None

    def render(self, name: str, item_name: str, /, **values: Any) -> str:
        """Render one template.

        ``name`` and ``item_name`` are positional-only so that ``name`` can also be a value:
        the standard placeholder list has a ``name`` placeholder.

        ``item_name`` is the name string that GUIDs of nested elements derive from:
        ``guid(role)`` gives ``format_guid(child_guid(item_name, role))``, and ``guid("self")``
        gives the item's own GUID, passed as ``self_guid`` (a ``uuid.UUID``). Other values are
        inserted as given, HTML/XML-escaped unless they are ``Markup``.
        """
        try:
            template = self._compiled[name]
        except KeyError:
            raise _fail(f"unknown template {name!r}") from None
        if "guid" in values:
            raise _fail(f"template {name!r}: 'guid' is reserved and cannot be a value")
        self_guid = values.pop("self_guid", None)
        if self_guid is not None and not isinstance(self_guid, uuid.UUID):
            raise _fail(f"template {name!r}: self_guid must be a uuid.UUID")
        guid = _make_guid(name, item_name, self_guid, self.format.guid_style)
        try:
            return template.render(guid=guid, **values)
        except jinja2.UndefinedError as exc:
            raise _fail(f"template {name!r} (item {item_name!r}): {exc.message}") from exc
        except jinja2.TemplateError as exc:
            raise _fail(f"template {name!r} (item {item_name!r}): {exc}") from exc


def _make_guid(
    template: str, item_name: str, self_guid: uuid.UUID | None, style: str
) -> Callable[[str], str]:
    def guid(role: str) -> str:
        if role == "self":
            if self_guid is None:
                raise _fail(f'template {template!r}: guid("self") used but no self_guid was given')
            return ids.format_guid(self_guid, style)
        return ids.format_guid(ids.child_guid(item_name, role), style)

    return guid
