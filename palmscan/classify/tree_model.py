"""Decision-tree species classifier trained on inventory-plus-LiDAR matches (plan W18).

Every inventory palm matched to a LiDAR crown is a labelled example: a known species and a measured
shape. :func:`train` fits a small tree on those, compares it by cross-validation with the hand
rules (:func:`palmscan.classify.species.shape_rules`) on the same samples, and returns it only when
it is better by at least ``ClassifyParams.tree_min_gain``. The rules stay as the fallback: the tree
answers ``None`` for the ``_other`` class and :func:`palmscan.classify.species.classify` then runs
the rules.

The model is stored as plain JSON (the sklearn tree arrays). :meth:`TreeModel.predict` walks those
arrays with numpy, so inference needs neither scikit-learn nor a pickle, and gives the same answer
on every machine. scikit-learn is imported only inside :func:`train` (extra ``lidar``).

Training is deterministic: samples are sorted by ``(stable_key, candidate_id)``, and the tree and
the folds use ``random_state=0``.

Accuracy figures produced here are on whatever data the caller passes; none are claimed for real
data. VERIFY: real-label accuracy comes with the ground truth of TEST-101.
"""

from __future__ import annotations

import json
import warnings
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final

import numpy as np

from palmcore.log import get_logger
from palmscan.classify.priors import FILIFERA, UNKNOWN_SPECIES
from palmscan.classify.species import (
    DEFAULT_SHAPE_RULES,
    FEATURES,
    ShapeRule,
    _registered_keys,
    shape_rules,
)
from palmscan.config import ClassifyParams
from palmscan.model import LidarCandidate, PalmRecord

__all__ = [
    "OTHER",
    "TrainReport",
    "TreeModel",
    "load_model",
    "save_model",
    "train",
]

log = get_logger(__name__)

OTHER: Final = "_other"  # rare or unusable labels; the tree answers None for them
FORMAT_VERSION: Final = 1
CONF_SCALE: Final = 0.9
CONF_MIN: Final = 0.3
CONF_MAX: Final = 0.85
N_FOLDS: Final = 5
RANDOM_STATE: Final = 0


@dataclass(slots=True)
class TrainReport:
    n_samples: int
    classes: list[str]
    cv_acc_tree: float | None
    cv_acc_rules: float
    used: bool
    reason: str  # "ok" | "too_few_samples" | "no_gain" | "disabled"
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)  # true -> predicted -> n


class TreeModel:
    """A fitted decision tree as numpy arrays. Implements ``ShapeModel``."""

    name: ClassVar[str] = "lidar_tree"

    def __init__(
        self,
        features: list[str],
        classes: list[str],
        children_left: np.ndarray,
        children_right: np.ndarray,
        feature: np.ndarray,
        threshold: np.ndarray,
        value: np.ndarray,
    ) -> None:
        n_nodes = len(children_left)
        if not (len(children_right) == len(feature) == len(threshold) == len(value) == n_nodes):
            raise ValueError("tree arrays have different lengths")
        if n_nodes == 0:
            raise ValueError("tree has no nodes")
        if value.shape != (n_nodes, len(classes)):
            raise ValueError(f"value has shape {value.shape}, expected {(n_nodes, len(classes))}")
        if features != FEATURES:
            raise ValueError(f"model features {features} do not match {FEATURES}")
        for cls in classes:
            if cls != OTHER:
                _check_label(cls)
        self.features = features
        self.classes = classes
        self.children_left = children_left
        self.children_right = children_right
        self.feature = feature
        self.threshold = threshold
        self.value = value

    def _leaves(self, X: np.ndarray) -> np.ndarray:
        # sklearn compares float32 features with float64 thresholds; do the same.
        Xf = np.asarray(X, dtype=np.float32)
        node = np.zeros(len(Xf), dtype=np.int64)
        rows = np.arange(len(Xf))
        while True:
            left = self.children_left[node]
            active = left != -1
            if not active.any():
                return node
            go_left = Xf[rows, self.feature[node]] <= self.threshold[node]
            nxt = np.where(go_left, left, self.children_right[node])
            node = np.where(active, nxt, node)

    def predict(self, X: np.ndarray) -> list[tuple[str | None, float]]:
        """One ``(species, confidence)`` per row; ``None`` for the ``_other`` class."""
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != len(self.features):
            raise ValueError(f"X must have shape (n, {len(self.features)}), got {X.shape}")
        if len(X) == 0:
            return []
        counts = self.value[self._leaves(X)]
        best = counts.argmax(axis=1)
        frac = counts[np.arange(len(X)), best] / counts.sum(axis=1)
        conf = np.clip(frac * CONF_SCALE, CONF_MIN, CONF_MAX)
        out: list[tuple[str | None, float]] = []
        for idx, c in zip(best, conf, strict=True):
            label = self.classes[int(idx)]
            out.append((None if label == OTHER else label, float(c)))
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "version": FORMAT_VERSION,
            "features": list(self.features),
            "classes": list(self.classes),
            "children_left": self.children_left.tolist(),
            "children_right": self.children_right.tolist(),
            "feature": self.feature.tolist(),
            "threshold": self.threshold.tolist(),
            "value": self.value.tolist(),
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> TreeModel:
        if d.get("version") != FORMAT_VERSION:
            raise ValueError(f"unsupported tree model version {d.get('version')!r}")
        try:
            return cls(
                features=[str(f) for f in d["features"]],
                classes=[str(c) for c in d["classes"]],
                children_left=np.asarray(d["children_left"], dtype=np.int64),
                children_right=np.asarray(d["children_right"], dtype=np.int64),
                feature=np.asarray(d["feature"], dtype=np.int64),
                threshold=np.asarray(d["threshold"], dtype=np.float64),
                value=np.asarray(d["value"], dtype=np.float64),
            )
        except KeyError as exc:
            raise ValueError(f"tree model JSON is missing {exc}") from exc


def save_model(model: TreeModel, path: Path) -> None:
    """Write ``species_tree.json`` (sorted keys, trailing newline, LF endings)."""
    text = json.dumps(model.to_json(), sort_keys=True, indent=1) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_model(path: Path) -> TreeModel:
    """Read a model saved by :func:`save_model` (``ClassifyParams.tree_model_path``)."""
    return TreeModel.from_json(json.loads(path.read_text(encoding="utf-8")))


def _check_label(species: str) -> None:
    if species not in _registered_keys():
        raise ValueError(f"tree class {species!r} is not in species_keys.yaml")
    if species == FILIFERA:
        raise ValueError(f"tree class {FILIFERA} is not allowed; shape classifiers never emit it")


def _label_of(species: str | None) -> str:
    """Training label: species key, filifera folded into robusta, anything else ``_other``."""
    if species is None or species == UNKNOWN_SPECIES:
        return OTHER
    if species == FILIFERA:
        return "washingtonia_robusta"
    return species if species in _registered_keys() else OTHER


def _row(cand: LidarCandidate) -> list[float]:
    values = {
        "height_m": cand.height_m,
        "crown_diam_m": cand.crown_diam_m,
        "ratio": cand.ratio,
        "shared_boundary_frac": cand.shared_boundary_frac,
    }
    return [float(values[name]) for name in FEATURES]


def _report(
    n: int, classes: list[str], acc_rules: float, reason: str, **kw: Any
) -> tuple[None, TrainReport]:
    return None, TrainReport(
        n_samples=n,
        classes=classes,
        cv_acc_tree=kw.get("cv_acc_tree"),
        cv_acc_rules=acc_rules,
        used=False,
        reason=reason,
        confusion=kw.get("confusion", {}),
    )


def train(
    training: Sequence[tuple[PalmRecord, LidarCandidate]],
    params: ClassifyParams,
    rules: Sequence[ShapeRule] = DEFAULT_SHAPE_RULES,
) -> tuple[TreeModel | None, TrainReport]:
    """Fit the tree and decide whether it beats the rules.

    ``training`` holds ``(inventory palm, matched candidate)`` pairs. The model is returned only
    with ``report.used`` true; otherwise it is ``None`` and ``report.reason`` says why.
    """
    if not params.use_tree:
        return _report(0, [], 0.0, "disabled")

    pairs = sorted(training, key=lambda pc: (pc[0].stable_key, pc[1].candidate_id))
    raw = [_label_of(palm.species) for palm, _ in pairs]
    # Labels with too few samples are merged into _other. _other itself may be of any size.
    n_by_label = Counter(raw)
    labels = [
        lab if lab == OTHER or n_by_label[lab] >= params.tree_min_class_n else OTHER for lab in raw
    ]
    n = len(labels)
    real = sorted({lab for lab in labels if lab != OTHER})
    classes = sorted(set(labels))

    # A rules answer of None is "no species", the same as the _other label (it falls through to
    # the priors), so it counts as right on _other samples. See the plan note in W18.
    X = np.array([_row(cand) for _, cand in pairs], dtype=float).reshape(n, len(FEATURES))
    rule_pred = [
        shape_rules(cand.height_m, cand.crown_diam_m, rules)[0] or OTHER for _, cand in pairs
    ]
    acc_rules = (
        float(np.mean([p == t for p, t in zip(rule_pred, labels, strict=True)])) if n else 0.0
    )

    if n < params.tree_min_total_n or len(real) < 2:
        log.info("species tree: %d samples, %d real classes: not trained", n, len(real))
        return _report(n, classes, acc_rules, "too_few_samples")

    # sklearn is imported here only, so inference never needs it (extra "lidar").
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.tree import DecisionTreeClassifier

    def make_tree() -> DecisionTreeClassifier:
        return DecisionTreeClassifier(
            max_depth=params.tree_max_depth,
            min_samples_leaf=params.tree_min_samples_leaf,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )

    y = np.array(labels)
    # Real classes have >= tree_min_class_n samples, but _other can be smaller than the fold count;
    # sklearn only warns then.
    folds = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*least populated class.*")
        oof = cross_val_predict(make_tree(), X, y, cv=folds)
    acc_tree = float(np.mean(oof == y))

    confusion: dict[str, dict[str, int]] = {c: {} for c in classes}
    for true, pred in zip(labels, oof.tolist(), strict=True):
        confusion[true][pred] = confusion[true].get(pred, 0) + 1
    confusion = {t: dict(sorted(row.items())) for t, row in sorted(confusion.items())}

    if acc_tree < acc_rules + params.tree_min_gain:
        log.info("species tree: cv %.3f vs rules %.3f, gain too small", acc_tree, acc_rules)
        return _report(n, classes, acc_rules, "no_gain", cv_acc_tree=acc_tree, confusion=confusion)

    fitted = make_tree().fit(X, y)
    t = fitted.tree_
    raw_value = np.asarray(t.value, dtype=float).reshape(t.node_count, len(fitted.classes_))
    model = TreeModel(
        features=list(FEATURES),
        classes=[str(c) for c in fitted.classes_],
        children_left=np.asarray(t.children_left, dtype=np.int64),
        children_right=np.asarray(t.children_right, dtype=np.int64),
        feature=np.asarray(t.feature, dtype=np.int64),
        threshold=np.asarray(t.threshold, dtype=np.float64),
        value=raw_value,
    )
    report = TrainReport(
        n_samples=n,
        classes=classes,
        cv_acc_tree=acc_tree,
        cv_acc_rules=acc_rules,
        used=True,
        reason="ok",
        confusion=confusion,
    )
    log.info("species tree: used, cv %.3f vs rules %.3f on %d samples", acc_tree, acc_rules, n)
    return model, report
