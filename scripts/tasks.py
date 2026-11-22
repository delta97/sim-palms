#!/usr/bin/env python3
"""Task tracker for sim-palms. Standard library only.

Tasks live in tracking/tasks/<ID>.md as Markdown with a small YAML-like
frontmatter block (see tracking/tasks/_TEMPLATE.md). This script reads and
edits that frontmatter so humans and agents share one source of truth.

Usage (run from anywhere inside the repo):
  python3 scripts/tasks.py list [--status S] [--area A] [--phase N] [--requires R] [--needs R] [--agent X]
  python3 scripts/tasks.py show ID
  python3 scripts/tasks.py ready [--requires none] [--agent X] [--phase N]
  python3 scripts/tasks.py batch [--requires none] [--max 4]   # parallel-safe set of ready tasks
  python3 scripts/tasks.py claim ID --owner WHO [--branch B] [--worktree W]
  python3 scripts/tasks.py set ID STATUS [--by WHO] [--note TEXT]
  python3 scripts/tasks.py log ID TEXT [--by WHO]
  python3 scripts/tasks.py new AREA --title TEXT [--phase N]   # allocates the next id from the template
  python3 scripts/tasks.py validate [--strict]
  python3 scripts/tasks.py conflicts                            # same-path tasks with no dependency ordering
  python3 scripts/tasks.py board                                # rewrites tracking/BOARD.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "tracking" / "tasks"
BOARD = ROOT / "tracking" / "BOARD.md"

STATUSES = ["todo", "in_progress", "blocked", "review", "done", "dropped"]
KINDS = ["build", "spike", "research", "decision", "test", "doc", "gate"]
REQUIRES = ["none", "windows-sim", "blender", "gpu", "network", "human"]
AREAS = ["ARCH", "SCAN", "GEN", "LIVE", "ASSET", "SPIKE", "TEST", "DEC", "RISK",
         "FX", "REGION", "GATE", "INFRA"]
REQUIRED_KEYS = ["id", "title", "status", "phase", "area", "kind", "plan_ref",
                 "depends_on", "requires", "agent", "estimate_h", "touches",
                 "owner", "branch", "worktree", "updated"]
REQUIRED_SECTIONS = ["Goal", "Steps", "Acceptance criteria", "Verification", "Log"]
ID_RE = re.compile(r"^(?:[A-Z]+-\d{3}|GATE-P\d)$")
STUB_MARKER = "STUB:"


def today() -> str:
    return _dt.date.today().isoformat()


# --------------------------------------------------------------------------- parsing

def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("["):
        end = raw.find("]")
        inner = raw[1:end if end != -1 else len(raw)].strip()
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        return raw[1:end] if end != -1 else raw[1:]
    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def _format_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},]|^\s|\s$", s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


@dataclass
class Task:
    path: Path
    meta: dict
    body: str
    fm_lines: list = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(self.meta.get("id", ""))

    def get_list(self, key) -> list:
        v = self.meta.get(key, [])
        if isinstance(v, list):
            return v
        return [v] if v not in ("", None) else []

    def set(self, key, value):
        self.meta[key] = value
        line = f"{key}: {_format_value(value)}"
        for i, l in enumerate(self.fm_lines):
            if re.match(rf"^{re.escape(key)}\s*:", l):
                self.fm_lines[i] = line
                return
        self.fm_lines.append(line)

    def append_log(self, who: str, text: str):
        entry = f"- {today()} [{who}] {text}"
        if re.search(r"^## Log\s*$", self.body, flags=re.M):
            self.body = self.body.rstrip("\n") + "\n" + entry + "\n"
        else:
            self.body = self.body.rstrip("\n") + "\n\n## Log\n\n" + entry + "\n"

    def save(self):
        self.set("updated", today())
        text = "---\n" + "\n".join(self.fm_lines) + "\n---\n" + self.body
        self.path.write_text(text, encoding="utf-8", newline="\n")


def load_task(path: Path) -> Task:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing frontmatter")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise ValueError(f"{path.name}: unterminated frontmatter")
    fm_block = text[4:end]
    body = text[end + 5:]
    meta, lines = {}, []
    for line in fm_block.splitlines():
        lines.append(line)
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1)] = _parse_value(m.group(2))
    return Task(path=path, meta=meta, body=body, fm_lines=lines)


def load_all() -> dict[str, Task]:
    tasks = {}
    for p in sorted(TASK_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue
        t = load_task(p)
        tasks[t.id or p.stem] = t
    return tasks


# --------------------------------------------------------------------------- logic

def is_ready(t: Task, tasks: dict[str, Task]) -> bool:
    if t.meta.get("status") != "todo":
        return False
    return all(tasks.get(d) is not None and tasks[d].meta.get("status") in ("done", "dropped")
               for d in t.get_list("depends_on"))


def _norm(p: str) -> str:
    return p.strip().lstrip("./")


def paths_overlap(a: list, b: list) -> list:
    hits = []
    for x in a:
        for y in b:
            x2, y2 = _norm(x), _norm(y)
            xs, ys = x2.rstrip("/"), y2.rstrip("/")
            if xs == ys or ys.startswith(xs + "/") or xs.startswith(ys + "/"):
                hits.append((x, y))
    return hits


def find_cycles(tasks: dict[str, Task]) -> list:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {k: WHITE for k in tasks}
    cycles, stack = [], []

    def visit(n):
        color[n] = GREY
        stack.append(n)
        for d in tasks[n].get_list("depends_on"):
            if d not in tasks:
                continue
            if color[d] == GREY:
                cycles.append(stack[stack.index(d):] + [d])
            elif color[d] == WHITE:
                visit(d)
        stack.pop()
        color[n] = BLACK

    sys.setrecursionlimit(10000)
    for k in tasks:
        if color[k] == WHITE:
            visit(k)
    return cycles


def ancestors(tasks: dict[str, Task]) -> dict[str, set]:
    """Transitive dependency closure for every task."""
    memo: dict[str, set] = {}

    def anc(n, seen=()):
        if n in memo:
            return memo[n]
        out = set()
        for d in tasks[n].get_list("depends_on"):
            if d in tasks and d not in seen:
                out.add(d)
                out |= anc(d, seen + (n,))
        memo[n] = out
        return out

    for k in tasks:
        anc(k)
    return memo


def unordered_conflicts(tasks: dict[str, Task]) -> list:
    """Pairs of open tasks that touch the same path with no dependency path between them."""
    anc = ancestors(tasks)
    live = sorted([t for t in tasks.values() if t.meta.get("status") not in ("done", "dropped")], key=lambda t: t.id)
    out = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            hits = paths_overlap(a.get_list("touches"), b.get_list("touches"))
            if hits and a.id not in anc[b.id] and b.id not in anc[a.id]:
                out.append((a.id, b.id, hits[0]))
    return out


def validate(tasks: dict[str, Task]) -> tuple[list, list]:
    errors, warnings = [], []
    for tid, t in tasks.items():
        m = t.meta
        where = t.path.name
        for k in REQUIRED_KEYS:
            if k not in m:
                errors.append(f"{where}: missing key '{k}'")
        if not ID_RE.match(tid):
            errors.append(f"{where}: bad id '{tid}'")
        if t.path.stem != tid:
            errors.append(f"{where}: filename does not match id '{tid}'")
        prefix = tid.split("-")[0]
        if m.get("area") != prefix:
            errors.append(f"{where}: area '{m.get('area')}' does not match id prefix '{prefix}'")
        if prefix not in AREAS:
            errors.append(f"{where}: unknown area '{prefix}'")
        if m.get("status") not in STATUSES:
            errors.append(f"{where}: bad status '{m.get('status')}'")
        if m.get("kind") not in KINDS:
            errors.append(f"{where}: bad kind '{m.get('kind')}'")
        if not isinstance(m.get("phase"), int) or not 0 <= m.get("phase") <= 7:
            errors.append(f"{where}: phase must be an integer 0-7")
        for r in t.get_list("requires"):
            if r not in REQUIRES:
                errors.append(f"{where}: bad requires value '{r}'")
        for d in t.get_list("depends_on"):
            if d == tid:
                errors.append(f"{where}: depends on itself")
            elif d not in tasks:
                errors.append(f"{where}: depends_on unknown task '{d}'")
            elif m.get("status") == "done" and tasks[d].meta.get("status") not in ("done", "dropped"):
                warnings.append(f"{where}: is done but dependency {d} is not")
        if m.get("status") in ("in_progress", "review") and not m.get("owner"):
            errors.append(f"{where}: status {m.get('status')} requires an owner")
        plan_ref = str(m.get("plan_ref", "")).split("#")[0]
        if plan_ref and not (ROOT / plan_ref).exists():
            warnings.append(f"{where}: plan_ref file not found: {plan_ref}")
        if STUB_MARKER in t.body:
            warnings.append(f"{where}: still a stub (contains '{STUB_MARKER}')")
        else:
            for s in REQUIRED_SECTIONS:
                if not re.search(rf"^## {re.escape(s)}\s*$", t.body, flags=re.M):
                    errors.append(f"{where}: missing section '## {s}'")
        if m.get("kind") != "gate" and not t.get_list("touches") and m.get("kind") in ("build", "test"):
            warnings.append(f"{where}: build/test task with empty 'touches'")
    for c in find_cycles(tasks):
        errors.append("dependency cycle: " + " -> ".join(c))
    active = [t for t in tasks.values() if t.meta.get("status") == "in_progress"]
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            hits = paths_overlap(a.get_list("touches"), b.get_list("touches"))
            if hits:
                warnings.append(f"parallel conflict: {a.id} and {b.id} both touch {hits[0]}")
    return errors, warnings


# --------------------------------------------------------------------------- output

def row(t: Task) -> str:
    m = t.meta
    return (f"{t.id:<10} {m.get('status',''):<11} P{m.get('phase','?')} "
            f"{','.join(t.get_list('requires')):<18} {str(m.get('agent','')):<28} {m.get('title','')}")


def _filter(tasks, a):
    out = []
    for t in tasks.values():
        m = t.meta
        if getattr(a, "status", None) and m.get("status") != a.status:
            continue
        if getattr(a, "area", None) and m.get("area") != a.area:
            continue
        if getattr(a, "phase", None) is not None and m.get("phase") != a.phase:
            continue
        if getattr(a, "agent", None) and m.get("agent") != a.agent:
            continue
        if getattr(a, "requires", None):
            allowed = set(a.requires.split(","))
            if not set(t.get_list("requires")) <= allowed:
                continue
        if getattr(a, "needs", None):
            if not set(t.get_list("requires")) & set(a.needs.split(",")):
                continue
        out.append(t)
    return sorted(out, key=lambda t: (t.meta.get("phase", 9), t.id))


def write_board(tasks: dict[str, Task]) -> str:
    lines = ["# Task Board", "",
             "<!-- GENERATED by `python3 scripts/tasks.py board`. Do not edit by hand.",
             "     On a merge conflict, accept either side and regenerate. -->", "",
             f"Generated: {today()}", ""]
    counts = {s: 0 for s in STATUSES}
    for t in tasks.values():
        counts[t.meta.get("status", "todo")] = counts.get(t.meta.get("status", "todo"), 0) + 1
    lines.append("| " + " | ".join(STATUSES) + " | total |")
    lines.append("|" + "---|" * (len(STATUSES) + 1))
    lines.append("| " + " | ".join(str(counts[s]) for s in STATUSES) + f" | {len(tasks)} |")
    lines.append("")

    def table(title, items, cols):
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            return
        lines.append("| " + " | ".join(c[0] for c in cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for t in items:
            lines.append("| " + " | ".join(c[1](t) for c in cols) + " |")
        lines.append("")

    link = lambda t: f"[{t.id}](tasks/{t.id}.md)"
    req = lambda t: ", ".join(t.get_list("requires"))
    active = sorted([t for t in tasks.values() if t.meta.get("status") in ("in_progress", "review")], key=lambda t: t.id)
    table("In progress / in review", active, [
        ("Task", link), ("Status", lambda t: t.meta.get("status")), ("Owner", lambda t: str(t.meta.get("owner"))),
        ("Branch", lambda t: str(t.meta.get("branch"))), ("Title", lambda t: str(t.meta.get("title")))])
    blocked = sorted([t for t in tasks.values() if t.meta.get("status") == "blocked"], key=lambda t: t.id)
    table("Blocked", blocked, [("Task", link), ("Title", lambda t: str(t.meta.get("title"))),
                                ("Depends on", lambda t: ", ".join(t.get_list("depends_on")))])
    ready = sorted([t for t in tasks.values() if is_ready(t, tasks)], key=lambda t: (t.meta.get("phase"), t.id))
    table("Ready now (all dependencies done)", ready, [
        ("Task", link), ("Phase", lambda t: str(t.meta.get("phase"))), ("Requires", req),
        ("Agent", lambda t: str(t.meta.get("agent"))), ("Title", lambda t: str(t.meta.get("title")))])
    for ph in range(0, 8):
        items = sorted([t for t in tasks.values() if t.meta.get("phase") == ph], key=lambda t: t.id)
        if not items:
            continue
        done = sum(1 for t in items if t.meta.get("status") == "done")
        table(f"Phase {ph} ({done}/{len(items)} done)", items, [
            ("Task", link), ("Status", lambda t: str(t.meta.get("status"))), ("Requires", req),
            ("Depends on", lambda t: ", ".join(t.get_list("depends_on"))), ("Title", lambda t: str(t.meta.get("title")))])
    text = "\n".join(lines).rstrip() + "\n"
    BOARD.write_text(text, encoding="utf-8", newline="\n")
    return text


# --------------------------------------------------------------------------- commands

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def filt(p):
        p.add_argument("--status")
        p.add_argument("--area")
        p.add_argument("--phase", type=int)
        p.add_argument("--agent")
        p.add_argument("--requires", help="comma list; keep tasks whose requires are a subset, e.g. none")
        p.add_argument("--needs", help="comma list; keep tasks whose requires include any of these, e.g. windows-sim,human")

    filt(sub.add_parser("list"))
    sub.add_parser("show").add_argument("id")
    filt(sub.add_parser("ready"))
    b = sub.add_parser("batch")
    filt(b)
    b.add_argument("--max", type=int, default=4)
    c = sub.add_parser("claim")
    c.add_argument("id")
    c.add_argument("--owner", required=True)
    c.add_argument("--branch", default="")
    c.add_argument("--worktree", default="")
    c.add_argument("--force", action="store_true", help="claim even if not ready")
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("status", choices=STATUSES)
    s.add_argument("--by", default="agent")
    s.add_argument("--note", default="")
    lg = sub.add_parser("log")
    lg.add_argument("id")
    lg.add_argument("text")
    lg.add_argument("--by", default="agent")
    n = sub.add_parser("new")
    n.add_argument("area", choices=AREAS)
    n.add_argument("--title", required=True)
    n.add_argument("--phase", type=int, default=0)
    v = sub.add_parser("validate")
    v.add_argument("--strict", action="store_true", help="treat warnings as errors")
    sub.add_parser("board")
    sub.add_parser("conflicts", help="open tasks touching the same path with no dependency ordering")
    a = ap.parse_args(argv)

    tasks = load_all()

    if a.cmd == "list":
        for t in _filter(tasks, a):
            print(row(t))
    elif a.cmd == "show":
        t = tasks.get(a.id) or sys.exit(f"no task {a.id}")
        print(t.path.read_text(encoding="utf-8"))
        deps = t.get_list("depends_on")
        if deps:
            print("Dependency status:")
            for d in deps:
                print(f"  {d}: {tasks[d].meta.get('status') if d in tasks else 'MISSING'}")
        print("Ready:", is_ready(t, tasks))
    elif a.cmd == "ready":
        for t in _filter(tasks, a):
            if is_ready(t, tasks):
                print(row(t))
    elif a.cmd == "batch":
        busy = [p for t in tasks.values() if t.meta.get("status") == "in_progress" for p in t.get_list("touches")]
        chosen, claimed = [], list(busy)
        for t in _filter(tasks, a):
            if not is_ready(t, tasks):
                continue
            if paths_overlap(t.get_list("touches"), claimed):
                continue
            chosen.append(t)
            claimed += t.get_list("touches")
            if len(chosen) >= a.max:
                break
        if not chosen:
            print("No parallel-safe ready tasks match.")
        for t in chosen:
            print(row(t))
    elif a.cmd == "claim":
        t = tasks.get(a.id) or sys.exit(f"no task {a.id}")
        if t.meta.get("status") != "todo" and not a.force:
            sys.exit(f"{a.id} is '{t.meta.get('status')}', not todo (owner: {t.meta.get('owner')!r}). Use --force to override.")
        if not is_ready(t, tasks) and not a.force:
            open_deps = [d for d in t.get_list("depends_on") if tasks.get(d) is None or tasks[d].meta.get("status") != "done"]
            sys.exit(f"{a.id} is not ready; open dependencies: {', '.join(open_deps)}. Use --force to override.")
        t.set("status", "in_progress")
        t.set("owner", a.owner)
        t.set("branch", a.branch)
        t.set("worktree", a.worktree)
        t.append_log(a.owner, f"Claimed. branch={a.branch or '-'} worktree={a.worktree or '-'}")
        t.save()
        print(f"claimed {a.id} for {a.owner}")
    elif a.cmd == "set":
        t = tasks.get(a.id) or sys.exit(f"no task {a.id}")
        old = t.meta.get("status")
        t.set("status", a.status)
        if a.status in ("todo",):
            t.set("owner", "")
        t.append_log(a.by, f"Status {old} -> {a.status}." + (f" {a.note}" if a.note else ""))
        t.save()
        print(f"{a.id}: {old} -> {a.status}")
    elif a.cmd == "log":
        t = tasks.get(a.id) or sys.exit(f"no task {a.id}")
        t.append_log(a.by, a.text)
        t.save()
    elif a.cmd == "new":
        nums = [int(k.split("-")[1]) for k in tasks if k.startswith(a.area + "-") and k.split("-")[1].isdigit()]
        ordinary = [x for x in nums if x < 100]
        nid = f"{a.area}-{(max(ordinary) + 1 if ordinary else 1):03d}"
        tmpl = (TASK_DIR / "_TEMPLATE.md").read_text(encoding="utf-8")
        tmpl = re.sub(r"<!--\nFIELD REFERENCE.*?-->\n\n", "", tmpl, flags=re.S)
        p = TASK_DIR / f"{nid}.md"
        p.write_text(tmpl, encoding="utf-8", newline="\n")
        t = load_task(p)
        t.set("id", nid)
        t.set("area", a.area)
        t.set("title", a.title)
        t.set("phase", a.phase)
        t.save()
        print(p.relative_to(ROOT))
    elif a.cmd == "validate":
        errors, warnings = validate(tasks)
        for w in warnings:
            print("WARN ", w)
        for e in errors:
            print("ERROR", e)
        print(f"{len(tasks)} tasks, {len(errors)} errors, {len(warnings)} warnings")
        if errors or (a.strict and warnings):
            sys.exit(1)
    elif a.cmd == "conflicts":
        found = unordered_conflicts(tasks)
        for x, y, (p1, p2) in found:
            print(f"{x:<10} {y:<10} {p1}" + (f"  ~ {p2}" if p2 != p1 else ""))
        print(f"{len(found)} unordered conflicts")
    elif a.cmd == "board":
        write_board(tasks)
        print(f"wrote {BOARD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
