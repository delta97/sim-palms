"""palmscan.classify.tree_model: training gate, JSON round trip, sklearn-free inference."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from palmscan.classify.species import FEATURES, classify, features_of
from palmscan.classify.tree_model import (
    OTHER,
    TreeModel,
    load_model,
    save_model,
    train,
)
from palmscan.config import ClassifyParams
from palmscan.model import LidarCandidate, PalmRecord

ROBUSTA = "washingtonia_robusta"
CANARY = "phoenix_canariensis"
QUEEN = "syagrus_romanzoffiana"
PARAMS = ClassifyParams()


def make_pair(
    key: str, species: str | None, h: float, c: float, shared: float = 0.1
) -> tuple[PalmRecord, LidarCandidate]:
    cand = LidarCandidate(
        candidate_id=f"d:t:{key}",
        dataset="d",
        x=0.0,
        y=0.0,
        lon=-117.2,
        lat=32.7,
        height_m=h,
        crown_area_m2=0.0,
        crown_diam_m=c,
        ratio=h / c,
        shared_boundary_frac=shared,
        ground_elev_m=None,
    )
    palm = PalmRecord(
        stable_key=key,
        lon=-117.2,
        lat=32.7,
        x=0.0,
        y=0.0,
        species=species,
        species_confidence=0.95,
        species_source="inventory",
        lidar=cand,
    )
    return palm, cand


def synth(kind: str, n_each: int = 30, seed: int = 0) -> list[tuple[PalmRecord, LidarCandidate]]:
    """Two classes. "tree_wins": shapes the hand rules miss. "rules_ok": shapes they get right."""
    rng = np.random.default_rng(seed)
    if kind == "tree_wins":
        specs = [(ROBUSTA, (9.0, 12.0), (2.5, 3.5)), (CANARY, (9.0, 12.0), (8.0, 10.0))]
    else:
        specs = [(ROBUSTA, (19.0, 25.0), (3.0, 4.5)), (CANARY, (10.0, 18.0), (7.5, 10.0))]
    out = []
    for species, (h0, h1), (c0, c1) in specs:
        for i in range(n_each):
            h = float(rng.uniform(h0, h1))
            c = float(rng.uniform(c0, c1))
            out.append(make_pair(f"{species}-{i:03d}", species, h, c))
    return out


def feature_matrix(pairs: list[tuple[PalmRecord, LidarCandidate]]) -> np.ndarray:
    return np.vstack([features_of(p) for p, _ in pairs])


def test_separable_data_uses_tree() -> None:
    model, report = train(synth("tree_wins"), PARAMS)
    assert model is not None
    assert report.used is True
    assert report.reason == "ok"
    assert report.n_samples == 60
    assert report.cv_acc_tree is not None
    assert report.cv_acc_tree >= report.cv_acc_rules + PARAMS.tree_min_gain
    assert report.cv_acc_tree > 0.9
    assert report.classes == [CANARY, ROBUSTA]
    assert sum(report.confusion[ROBUSTA].values()) == 30


def test_thirty_samples_is_too_few() -> None:
    model, report = train(synth("tree_wins", n_each=15), PARAMS)
    assert model is None
    assert report.used is False
    assert report.reason == "too_few_samples"
    assert report.n_samples == 30


def test_one_real_class_is_too_few() -> None:
    pairs = [make_pair(f"r{i:03d}", ROBUSTA, 20.0 + i % 3, 3.0) for i in range(60)]
    model, report = train(pairs, PARAMS)
    assert model is None
    assert report.reason == "too_few_samples"


def test_rules_already_perfect_gives_no_gain() -> None:
    model, report = train(synth("rules_ok"), PARAMS)
    assert model is None
    assert report.used is False
    assert report.reason == "no_gain"
    assert report.cv_acc_rules == 1.0
    assert report.cv_acc_tree is not None
    assert report.cv_acc_tree < report.cv_acc_rules + PARAMS.tree_min_gain
    assert report.confusion  # reported even when the tree is not used


def test_gain_threshold_is_the_gate() -> None:
    _, report = train(synth("tree_wins"), PARAMS)
    assert report.cv_acc_tree is not None
    gain = report.cv_acc_tree - report.cv_acc_rules
    model, strict = train(synth("tree_wins"), replace(PARAMS, tree_min_gain=gain + 0.01))
    assert model is None
    assert strict.reason == "no_gain"


def test_disabled() -> None:
    model, report = train(synth("tree_wins"), replace(PARAMS, use_tree=False))
    assert model is None
    assert report.reason == "disabled"
    assert report.used is False


def test_rare_class_becomes_other_and_falls_through() -> None:
    pairs = synth("tree_wins")
    pairs += [make_pair(f"q{i:03d}", QUEEN, 12.0, 5.5) for i in range(5)]  # < tree_min_class_n
    model, report = train(pairs, PARAMS)
    assert model is not None
    assert OTHER in report.classes
    assert QUEEN not in report.classes
    answers = model.predict(np.array([[12.0, 5.5, 12.0 / 5.5, 0.1]]))
    assert answers[0][0] is None  # _other: the rules get the palm


def test_filifera_labels_fold_into_robusta() -> None:
    pairs = synth("tree_wins")
    for palm, _ in pairs:
        if palm.species == ROBUSTA:
            palm.species = "washingtonia_filifera"
    model, report = train(pairs, PARAMS)
    assert model is not None
    assert "washingtonia_filifera" not in report.classes
    assert ROBUSTA in report.classes
    assert ROBUSTA in {s for s, _ in model.predict(feature_matrix(pairs))}


def test_training_is_deterministic_and_order_independent() -> None:
    pairs = synth("tree_wins")
    m1, r1 = train(pairs, PARAMS)
    m2, r2 = train(list(reversed(pairs)), PARAMS)
    assert m1 is not None and m2 is not None
    assert m1.to_json() == m2.to_json()
    assert r1 == r2


def test_confidence_is_clamped_and_species_registered() -> None:
    model, _ = train(synth("tree_wins"), PARAMS)
    assert model is not None
    X = np.array([[10.0, 3.0, 3.3, 0.1], [10.0, 9.0, 1.1, 0.1]])
    answers = model.predict(X)
    assert [s for s, _ in answers] == [ROBUSTA, CANARY]
    assert all(0.3 <= conf <= 0.85 for _, conf in answers)


def test_json_round_trip_gives_identical_predictions(tmp_path: Path) -> None:
    pairs = synth("tree_wins")
    model, _ = train(pairs, PARAMS)
    assert model is not None
    X = feature_matrix(pairs)
    again = TreeModel.from_json(json.loads(json.dumps(model.to_json())))
    assert again.predict(X) == model.predict(X)
    assert again.to_json() == model.to_json()

    path = tmp_path / "sub" / "species_tree.json"
    save_model(model, path)
    assert b"\r" not in path.read_bytes()
    assert path.read_bytes().endswith(b"\n")
    assert load_model(path).predict(X) == model.predict(X)


def test_predict_matches_sklearn() -> None:
    from sklearn.tree import DecisionTreeClassifier

    pairs = synth("tree_wins")
    model, _ = train(pairs, PARAMS)
    assert model is not None
    X = feature_matrix(pairs)
    y = np.array([p.species for p, _ in pairs])
    ref = DecisionTreeClassifier(
        max_depth=4, min_samples_leaf=5, class_weight="balanced", random_state=0
    ).fit(X, y)
    assert [s for s, _ in model.predict(X)] == ref.predict(X).tolist()


def test_predict_without_sklearn(monkeypatch: pytest.MonkeyPatch) -> None:
    model, _ = train(synth("tree_wins"), PARAMS)
    assert model is not None
    X = np.array([[10.0, 3.0, 3.3, 0.1], [10.0, 9.0, 1.1, 0.1]])
    expected = model.predict(X)
    saved = model.to_json()
    for name in [m for m in sys.modules if m == "sklearn" or m.startswith("sklearn.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "sklearn", None)
    with pytest.raises(ImportError):
        import sklearn  # noqa: F401
    assert model.predict(X) == expected
    assert TreeModel.from_json(saved).predict(X) == expected


def test_from_json_rejects_bad_models() -> None:
    model, _ = train(synth("tree_wins"), PARAMS)
    assert model is not None
    good = model.to_json()
    with pytest.raises(ValueError, match="version"):
        TreeModel.from_json({**good, "version": 99})
    with pytest.raises(ValueError, match="missing"):
        TreeModel.from_json({k: v for k, v in good.items() if k != "threshold"})
    with pytest.raises(ValueError, match="species_keys"):
        TreeModel.from_json({**good, "classes": ["not_a_species", ROBUSTA]})
    with pytest.raises(ValueError, match="filifera"):
        TreeModel.from_json({**good, "classes": ["washingtonia_filifera", ROBUSTA]})
    with pytest.raises(ValueError, match="features"):
        TreeModel.from_json({**good, "features": ["height_m"]})


def test_predict_checks_shape() -> None:
    model, _ = train(synth("tree_wins"), PARAMS)
    assert model is not None
    assert model.predict(np.empty((0, len(FEATURES)))) == []
    with pytest.raises(ValueError, match="shape"):
        model.predict(np.zeros((2, 3)))


def test_plugs_into_classify_with_rule_fallback() -> None:
    model, _ = train(synth("tree_wins"), PARAMS)
    assert model is not None
    palm, _ = make_pair("a", None, 10.0, 3.0)  # the rules say None here; the tree knows robusta
    palm.species_confidence = None
    palm.species_source = None
    classify([palm], {}, model=model)
    assert (palm.species, palm.species_source) == (ROBUSTA, "lidar_tree")
    assert 0.3 <= (palm.species_confidence or 0) <= 0.85

    # In the _other region the tree answers None and the rules decide.
    other = synth("tree_wins") + [make_pair(f"q{i}", QUEEN, 12.0, 5.5) for i in range(5)]
    model2, _ = train(other, PARAMS)
    assert model2 is not None
    palm2, _ = make_pair("b", None, 12.0, 5.5)
    palm2.species_confidence = None
    palm2.species_source = None
    classify([palm2], {}, model=model2)
    assert (palm2.species, palm2.species_source) == (QUEEN, "lidar_rules")
