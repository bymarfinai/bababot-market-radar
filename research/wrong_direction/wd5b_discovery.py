from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WD5B_VERSION = "wd5b-causal-discriminator-v1"
DATA_PATH = Path("/app/data/wd5a_causal_entry_features.csv")
MANIFEST_PATH = Path("/app/data/wd5a_feature_manifest.json")
OUTPUT_PATH = Path("/app/data/wd5b_discriminator_results.json")

REVERSE = "OPPOSITE_FROM_ENTRY_WIN"
NO_TRADE = "NO_TRADE_TARGET"
PRIMARY_LABELS = {REVERSE, NO_TRADE}

TIME_FEATURES = {
    "f_decision_hour_utc",
    "f_decision_hour_sin",
    "f_decision_hour_cos",
    "f_decision_weekday_utc",
}
SCALE_PROXY_FEATURES = {
    "f_context_quote_volume_5m",
    "f_context_quote_volume_24h",
    "f_context_regime_ema7",
    "f_context_regime_ema20",
}


def _f(value: Any) -> float:
    return float(value)


def load_rows() -> tuple[list[dict[str, str]], dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text())
    rows = list(csv.DictReader(DATA_PATH.open()))
    rows = [
        row for row in rows
        if row["target_strict_1_to_1"] in PRIMARY_LABELS
    ]
    rows.sort(key=lambda row: int(row["meta_opened_at_ms"]))
    if len(rows) != 821:
        raise RuntimeError(f"expected 821 primary rows, got {len(rows)}")
    return rows, manifest


def label(row: dict[str, str]) -> int:
    return 1 if row["target_strict_1_to_1"] == REVERSE else 0


def split_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    n = len(rows)
    p40 = 2 * n // 5
    p60 = 3 * n // 5
    p80 = 4 * n // 5
    return {
        "inner_train": rows[:p40],
        "inner_val": rows[p40:p60],
        "dev": rows[:p60],
        "outer_val": rows[p60:p80],
        "dev_plus_val": rows[:p80],
        "test": rows[p80:],
    }


def feature_variants(manifest: dict[str, Any]) -> dict[str, list[str]]:
    all_features = list(manifest["model_feature_columns"])
    portable = [
        f for f in all_features
        if f not in TIME_FEATURES
        and f not in SCALE_PROXY_FEATURES
        and not f.startswith("f_latency_")
    ]
    return {
        "portable_market": portable,
        "full_causal_sensitivity": all_features,
    }


def feature_types(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        item["feature"]: item["type"]
        for item in manifest["feature_manifest"]
    }


def auc_score(y: list[int], p: list[float]) -> float | None:
    pos = [(score, target) for score, target in zip(p, y) if target == 1]
    n_pos = len(pos)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranked = sorted(zip(p, y), key=lambda x: x[0])
    rank_sum = 0.0
    i = 0
    rank = 1
    while i < len(ranked):
        j = i + 1
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        avg_rank = (rank + (rank + (j - i) - 1)) / 2.0
        rank_sum += avg_rank * sum(t for _, t in ranked[i:j])
        rank += j - i
        i = j
    u = rank_sum - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def binary_metrics(
    y: list[int],
    p: list[float],
    threshold: float = 0.5,
) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for target, prob in zip(y, p):
        pred = int(prob >= threshold)
        if target == 1 and pred == 1:
            tp += 1
        elif target == 0 and pred == 1:
            fp += 1
        elif target == 0 and pred == 0:
            tn += 1
        else:
            fn += 1
    rev_precision = tp / (tp + fp) if tp + fp else None
    rev_recall = tp / (tp + fn) if tp + fn else None
    no_precision = tn / (tn + fn) if tn + fn else None
    no_recall = tn / (tn + fp) if tn + fp else None
    bal = None
    if rev_recall is not None and no_recall is not None:
        bal = (rev_recall + no_recall) / 2.0
    return {
        "n": len(y),
        "auc": auc_score(y, p),
        "accuracy": (tp + tn) / len(y) if y else None,
        "balanced_accuracy": bal,
        "reverse_precision": rev_precision,
        "reverse_recall": rev_recall,
        "no_trade_precision": no_precision,
        "no_trade_recall": no_recall,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "reverse_prevalence": sum(y) / len(y) if y else None,
    }


def numeric_separation(rows: list[dict[str, str]], feature: str) -> dict[str, Any]:
    reverse = [_f(r[feature]) for r in rows if label(r) == 1]
    no_trade = [_f(r[feature]) for r in rows if label(r) == 0]
    if not reverse or not no_trade:
        return {"score": 0.0, "direction": 0, "auc": None}
    y = [0] * len(no_trade) + [1] * len(reverse)
    p = no_trade + reverse
    auc = auc_score(y, p)
    score = abs(float(auc) - 0.5) * 2.0 if auc is not None else 0.0
    med_rev = statistics.median(reverse)
    med_no = statistics.median(no_trade)
    return {
        "score": score,
        "direction": 1 if med_rev > med_no else (-1 if med_rev < med_no else 0),
        "auc": auc,
        "reverse_median": med_rev,
        "no_trade_median": med_no,
    }


def categorical_separation(
    rows: list[dict[str, str]],
    feature: str,
) -> dict[str, Any]:
    base = sum(label(r) for r in rows) / len(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[row[feature]].append(label(row))
    weighted = 0.0
    rates = {}
    for value, ys in groups.items():
        rate = sum(ys) / len(ys)
        rates[value] = {"n": len(ys), "reverse_rate": rate}
        weighted += (len(ys) / len(rows)) * abs(rate - base)
    return {
        "score": min(1.0, 2.0 * weighted),
        "category_rates": rates,
        "unique": len(groups),
    }


def rank_features(
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
) -> list[dict[str, Any]]:
    ranked = []
    for feature in features:
        if types[feature] == "numeric":
            info = numeric_separation(rows, feature)
        else:
            info = categorical_separation(rows, feature)
        ranked.append({"feature": feature, "type": types[feature], **info})
    ranked.sort(key=lambda x: (x["score"], x["feature"]), reverse=True)
    return ranked


class Encoder:
    def __init__(self, raw_features: list[str], types: dict[str, str]) -> None:
        self.raw_features = raw_features
        self.types = types
        self.numeric_stats: dict[str, tuple[float, float]] = {}
        self.categories: dict[str, list[str]] = {}
        self.encoded_names: list[str] = []

    def fit(self, rows: list[dict[str, str]]) -> "Encoder":
        names = []
        for feature in self.raw_features:
            if self.types[feature] == "numeric":
                vals = [_f(r[feature]) for r in rows]
                mean = sum(vals) / len(vals)
                var = sum((x - mean) ** 2 for x in vals) / len(vals)
                std = math.sqrt(var)
                self.numeric_stats[feature] = (mean, std if std > 1e-12 else 1.0)
                names.append(feature)
            else:
                cats = sorted({r[feature] for r in rows})
                self.categories[feature] = cats
                for cat in cats[1:]:
                    names.append(f"{feature}=={cat}")
        self.encoded_names = names
        return self

    def transform(self, rows: list[dict[str, str]]) -> list[list[float]]:
        matrix = []
        for row in rows:
            x = []
            for feature in self.raw_features:
                if self.types[feature] == "numeric":
                    mean, std = self.numeric_stats[feature]
                    x.append((_f(row[feature]) - mean) / std)
                else:
                    cats = self.categories[feature]
                    value = row[feature]
                    for cat in cats[1:]:
                        x.append(1.0 if value == cat else 0.0)
            matrix.append(x)
        return matrix


class LogisticModel:
    def __init__(self, l2: float = 0.1, epochs: int = 700, lr: float = 0.12) -> None:
        self.l2 = l2
        self.epochs = epochs
        self.lr = lr
        self.weights: list[float] = []
        self.epochs_run = 0

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z >= 0:
            e = math.exp(-min(z, 50.0))
            return 1.0 / (1.0 + e)
        e = math.exp(max(z, -50.0))
        return e / (1.0 + e)

    def fit(self, x: list[list[float]], y: list[int]) -> "LogisticModel":
        d = len(x[0]) if x else 0
        prevalence = min(0.999, max(0.001, sum(y) / len(y)))
        w = [math.log(prevalence / (1.0 - prevalence))] + [0.0] * d
        n = len(y)
        for epoch in range(self.epochs):
            grad = [0.0] * (d + 1)
            for row, target in zip(x, y):
                z = w[0]
                for j, value in enumerate(row, 1):
                    z += w[j] * value
                err = self._sigmoid(z) - target
                grad[0] += err
                for j, value in enumerate(row, 1):
                    grad[j] += err * value
            grad[0] /= n
            for j in range(1, d + 1):
                grad[j] = grad[j] / n + self.l2 * w[j] / max(1, d)
            rate = self.lr / (1.0 + 0.004 * epoch)
            max_step = 0.0
            for j in range(d + 1):
                step = rate * grad[j]
                w[j] -= step
                max_step = max(max_step, abs(step))
            self.epochs_run = epoch + 1
            if max_step < 1e-7:
                break
        self.weights = w
        return self

    def predict_proba(self, x: list[list[float]]) -> list[float]:
        out = []
        for row in x:
            z = self.weights[0]
            for j, value in enumerate(row, 1):
                z += self.weights[j] * value
            out.append(self._sigmoid(z))
        return out


def train_model(
    train_rows: list[dict[str, str]],
    eval_rows: list[dict[str, str]],
    raw_features: list[str],
    types: dict[str, str],
    l2: float,
) -> tuple[LogisticModel, Encoder, list[float]]:
    encoder = Encoder(raw_features, types).fit(train_rows)
    x_train = encoder.transform(train_rows)
    x_eval = encoder.transform(eval_rows)
    y_train = [label(r) for r in train_rows]
    model = LogisticModel(l2=l2).fit(x_train, y_train)
    return model, encoder, model.predict_proba(x_eval)


def select_hyperparams(
    inner_train: list[dict[str, str]],
    inner_val: list[dict[str, str]],
    candidate_features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    ranking = rank_features(inner_train, candidate_features, types)
    ordered = [item["feature"] for item in ranking]
    ks = [5, 10, 20, 30, 50, min(80, len(ordered)), len(ordered)]
    ks = sorted(set(k for k in ks if 1 <= k <= len(ordered)))
    l2_values = [0.01, 0.1, 0.5, 1.5, 4.0]
    results = []
    y_val = [label(r) for r in inner_val]
    for k in ks:
        features = ordered[:k]
        for l2 in l2_values:
            model, encoder, probs = train_model(
                inner_train, inner_val, features, types, l2
            )
            metrics = binary_metrics(y_val, probs)
            results.append({
                "top_k": k,
                "l2": l2,
                "auc": metrics["auc"],
                "balanced_accuracy_0p5": metrics["balanced_accuracy"],
                "accuracy_0p5": metrics["accuracy"],
                "encoded_feature_count": len(encoder.encoded_names),
                "epochs_run": model.epochs_run,
                "raw_features": features,
            })
    results.sort(
        key=lambda r: (
            r["auc"] if r["auc"] is not None else -1.0,
            r["balanced_accuracy_0p5"] if r["balanced_accuracy_0p5"] is not None else -1.0,
            -r["top_k"],
        ),
        reverse=True,
    )
    return {
        "feature_ranking_inner_train": ranking,
        "grid": results,
        "selected": results[0],
    }


def triage_metrics(
    y: list[int],
    p: list[float],
    lower: float,
    upper: float,
) -> dict[str, Any]:
    reverse_idx = [i for i, prob in enumerate(p) if prob >= upper]
    no_idx = [i for i, prob in enumerate(p) if prob <= lower]
    decided = set(reverse_idx) | set(no_idx)
    rev_correct = sum(y[i] == 1 for i in reverse_idx)
    no_correct = sum(y[i] == 0 for i in no_idx)
    rev_precision = rev_correct / len(reverse_idx) if reverse_idx else None
    no_precision = no_correct / len(no_idx) if no_idx else None
    return {
        "lower": lower,
        "upper": upper,
        "n": len(y),
        "reverse_n": len(reverse_idx),
        "no_trade_n": len(no_idx),
        "abstain_n": len(y) - len(decided),
        "coverage_pct": 100.0 * len(decided) / len(y) if y else None,
        "reverse_precision": rev_precision,
        "reverse_recall": (
            rev_correct / sum(y) if sum(y) else None
        ),
        "no_trade_precision": no_precision,
        "no_trade_recall": (
            no_correct / (len(y) - sum(y))
            if len(y) - sum(y) else None
        ),
        "decided_accuracy": (
            (rev_correct + no_correct) / len(decided)
            if decided else None
        ),
    }


def choose_triage_thresholds(y: list[int], p: list[float]) -> dict[str, Any]:
    values = sorted(set(round(x, 6) for x in p))
    if len(values) > 80:
        values = [
            values[round(i * (len(values) - 1) / 79)]
            for i in range(80)
        ]
        values = sorted(set(values))
    candidates = []
    for lower in values:
        for upper in values:
            if lower >= upper:
                continue
            m = triage_metrics(y, p, lower, upper)
            if m["reverse_n"] < 10 or m["no_trade_n"] < 10:
                continue
            candidates.append(m)

    chosen = None
    chosen_target = None
    for target in (0.80, 0.75, 0.70, 0.65, 0.60):
        eligible = [
            m for m in candidates
            if m["reverse_precision"] is not None
            and m["no_trade_precision"] is not None
            and m["reverse_precision"] >= target
            and m["no_trade_precision"] >= target
        ]
        if eligible:
            eligible.sort(
                key=lambda m: (
                    m["coverage_pct"],
                    min(m["reverse_precision"], m["no_trade_precision"]),
                    m["decided_accuracy"],
                ),
                reverse=True,
            )
            chosen = eligible[0]
            chosen_target = target
            break

    if chosen is None and candidates:
        candidates.sort(
            key=lambda m: (
                min(m["reverse_precision"], m["no_trade_precision"])
                * math.sqrt(max(0.0, m["coverage_pct"] / 100.0)),
                m["coverage_pct"],
            ),
            reverse=True,
        )
        chosen = candidates[0]
        chosen_target = None

    return {
        "selected_precision_floor": chosen_target,
        "selected": chosen,
        "frontier_top": sorted(
            candidates,
            key=lambda m: (
                min(m["reverse_precision"], m["no_trade_precision"]),
                m["coverage_pct"],
            ),
            reverse=True,
        )[:20],
    }


def feature_stability(
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
) -> list[dict[str, Any]]:
    n = len(rows)
    fifths = [
        rows[i * n // 5:(i + 1) * n // 5]
        for i in range(5)
    ]
    full_rank = rank_features(rows, features, types)
    out = []
    for item in full_rank:
        scores = []
        directions = []
        for part in fifths:
            if types[item["feature"]] == "numeric":
                info = numeric_separation(part, item["feature"])
                directions.append(info["direction"])
            else:
                info = categorical_separation(part, item["feature"])
            scores.append(info["score"])
        sign_consistent = None
        if types[item["feature"]] == "numeric":
            nonzero = [d for d in directions if d != 0]
            sign_consistent = len(set(nonzero)) <= 1 if nonzero else True
        out.append({
            "feature": item["feature"],
            "type": item["type"],
            "full_score": item["score"],
            "fifth_scores": scores,
            "median_fifth_score": statistics.median(scores),
            "min_fifth_score": min(scores),
            "numeric_direction_consistent": sign_consistent,
        })
    out.sort(
        key=lambda x: (
            x["median_fifth_score"],
            x["min_fifth_score"],
            x["full_score"],
        ),
        reverse=True,
    )
    return out


def analyze_variant(
    name: str,
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    splits = split_rows(rows)
    search = select_hyperparams(
        splits["inner_train"],
        splits["inner_val"],
        features,
        types,
    )
    selected = search["selected"]
    chosen_features = list(selected["raw_features"])

    model, encoder, val_probs = train_model(
        splits["dev"],
        splits["outer_val"],
        chosen_features,
        types,
        float(selected["l2"]),
    )
    y_val = [label(r) for r in splits["outer_val"]]
    val_binary = binary_metrics(y_val, val_probs)
    triage = choose_triage_thresholds(y_val, val_probs)

    # Final test remains untouched until model + thresholds are fixed.
    test_probs = model.predict_proba(encoder.transform(splits["test"]))
    y_test = [label(r) for r in splits["test"]]
    test_binary = binary_metrics(y_test, test_probs)

    selected_triage = triage["selected"]
    test_triage = None
    if selected_triage is not None:
        test_triage = triage_metrics(
            y_test,
            test_probs,
            float(selected_triage["lower"]),
            float(selected_triage["upper"]),
        )

    seen_symbols = {r["meta_symbol"] for r in splits["dev_plus_val"]}
    novel_indices = [
        i for i, row in enumerate(splits["test"])
        if row["meta_symbol"] not in seen_symbols
    ]
    novel_metrics = None
    novel_triage = None
    if novel_indices:
        novel_y = [y_test[i] for i in novel_indices]
        novel_p = [test_probs[i] for i in novel_indices]
        novel_metrics = binary_metrics(novel_y, novel_p)
        if selected_triage is not None:
            novel_triage = triage_metrics(
                novel_y,
                novel_p,
                float(selected_triage["lower"]),
                float(selected_triage["upper"]),
            )

    return {
        "variant": name,
        "candidate_feature_count": len(features),
        "hyperparameter_search": {
            "selected": {
                k: v for k, v in selected.items()
                if k != "raw_features"
            },
            "top_grid": [
                {k: v for k, v in item.items() if k != "raw_features"}
                for item in search["grid"][:12]
            ],
            "selected_raw_features": chosen_features,
            "inner_train_n": len(splits["inner_train"]),
            "inner_val_n": len(splits["inner_val"]),
        },
        "outer_validation": {
            "n": len(splits["outer_val"]),
            "binary_0p5": val_binary,
            "triage_selection": triage,
        },
        "final_test": {
            "n": len(splits["test"]),
            "binary_0p5": test_binary,
            "triage": test_triage,
            "novel_symbol_n": len(novel_indices),
            "novel_symbol_binary_0p5": novel_metrics,
            "novel_symbol_triage": novel_triage,
        },
        "model": {
            "encoded_feature_count": len(encoder.encoded_names),
            "encoded_names": encoder.encoded_names,
            "weights": model.weights,
            "epochs_run": model.epochs_run,
        },
    }




def _gini_from_counts(pos: int, total: int) -> float:
    if total <= 0:
        return 0.0
    p = pos / total
    return 2.0 * p * (1.0 - p)


class RandomTree:
    def __init__(
        self,
        max_depth: int,
        min_leaf: int,
        mtry: int,
        seed: int,
    ) -> None:
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.mtry = mtry
        self.rng = random.Random(seed)
        self.root: dict[str, Any] | None = None

    def _candidate_thresholds(
        self,
        x: list[list[float]],
        indices: list[int],
        feature: int,
    ) -> list[float]:
        vals = sorted({x[i][feature] for i in indices})
        if len(vals) <= 1:
            return []
        if len(vals) <= 6:
            return [(a + b) / 2.0 for a, b in zip(vals, vals[1:])]
        qs = (0.15, 0.30, 0.50, 0.70, 0.85)
        thresholds = []
        for q in qs:
            pos = int(q * (len(vals) - 1))
            if pos >= len(vals) - 1:
                continue
            thresholds.append((vals[pos] + vals[pos + 1]) / 2.0)
        return sorted(set(thresholds))

    def _build(
        self,
        x: list[list[float]],
        y: list[int],
        indices: list[int],
        depth: int,
    ) -> dict[str, Any]:
        pos = sum(y[i] for i in indices)
        n = len(indices)
        probability = (pos + 1.0) / (n + 2.0)
        node: dict[str, Any] = {
            "leaf": True,
            "probability": probability,
            "n": n,
            "pos": pos,
        }
        if (
            depth >= self.max_depth
            or n < 2 * self.min_leaf
            or pos == 0
            or pos == n
        ):
            return node

        d = len(x[0])
        features = list(range(d))
        self.rng.shuffle(features)
        features = features[:min(self.mtry, d)]
        parent_gini = _gini_from_counts(pos, n)
        best = None
        best_gain = 0.0

        for feature in features:
            for threshold in self._candidate_thresholds(x, indices, feature):
                left = [i for i in indices if x[i][feature] <= threshold]
                right = [i for i in indices if x[i][feature] > threshold]
                if len(left) < self.min_leaf or len(right) < self.min_leaf:
                    continue
                left_pos = sum(y[i] for i in left)
                right_pos = pos - left_pos
                weighted = (
                    len(left) / n * _gini_from_counts(left_pos, len(left))
                    + len(right) / n * _gini_from_counts(right_pos, len(right))
                )
                gain = parent_gini - weighted
                if gain > best_gain:
                    best_gain = gain
                    best = (feature, threshold, left, right)

        if best is None:
            return node

        feature, threshold, left, right = best
        return {
            "leaf": False,
            "feature": feature,
            "threshold": threshold,
            "gain": best_gain,
            "probability": probability,
            "n": n,
            "left": self._build(x, y, left, depth + 1),
            "right": self._build(x, y, right, depth + 1),
        }

    def fit(self, x: list[list[float]], y: list[int]) -> "RandomTree":
        n = len(y)
        bootstrap = [self.rng.randrange(n) for _ in range(n)]
        self.root = self._build(x, y, bootstrap, 0)
        return self

    def _predict_one(self, row: list[float]) -> float:
        node = self.root
        assert node is not None
        while not node["leaf"]:
            if row[node["feature"]] <= node["threshold"]:
                node = node["left"]
            else:
                node = node["right"]
        return float(node["probability"])

    def predict_proba(self, x: list[list[float]]) -> list[float]:
        return [self._predict_one(row) for row in x]


class RandomForestModel:
    def __init__(
        self,
        trees: int = 60,
        max_depth: int = 3,
        min_leaf: int = 18,
        seed: int = 20261001,
    ) -> None:
        self.trees = trees
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.seed = seed
        self.models: list[RandomTree] = []

    def fit(self, x: list[list[float]], y: list[int]) -> "RandomForestModel":
        d = len(x[0])
        mtry = max(3, int(math.sqrt(d)))
        self.models = []
        for i in range(self.trees):
            tree = RandomTree(
                max_depth=self.max_depth,
                min_leaf=self.min_leaf,
                mtry=mtry,
                seed=self.seed + i * 7919,
            ).fit(x, y)
            self.models.append(tree)
        return self

    def predict_proba(self, x: list[list[float]]) -> list[float]:
        sums = [0.0] * len(x)
        for tree in self.models:
            probs = tree.predict_proba(x)
            for i, p in enumerate(probs):
                sums[i] += p
        return [v / len(self.models) for v in sums]


def train_forest(
    train_rows: list[dict[str, str]],
    eval_rows: list[dict[str, str]],
    raw_features: list[str],
    types: dict[str, str],
    max_depth: int,
    min_leaf: int,
) -> tuple[RandomForestModel, Encoder, list[float]]:
    encoder = Encoder(raw_features, types).fit(train_rows)
    x_train = encoder.transform(train_rows)
    x_eval = encoder.transform(eval_rows)
    y_train = [label(r) for r in train_rows]
    model = RandomForestModel(
        trees=60,
        max_depth=max_depth,
        min_leaf=min_leaf,
    ).fit(x_train, y_train)
    return model, encoder, model.predict_proba(x_eval)


def select_forest_hyperparams(
    inner_train: list[dict[str, str]],
    inner_val: list[dict[str, str]],
    candidate_features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    ranking = rank_features(inner_train, candidate_features, types)
    ordered = [item["feature"] for item in ranking]
    y_val = [label(r) for r in inner_val]
    results = []
    for k in (10, 20, 40):
        features = ordered[:min(k, len(ordered))]
        for depth in (2, 3, 4):
            for min_leaf in (15, 25):
                model, encoder, probs = train_forest(
                    inner_train,
                    inner_val,
                    features,
                    types,
                    max_depth=depth,
                    min_leaf=min_leaf,
                )
                metrics = binary_metrics(y_val, probs)
                results.append({
                    "top_k": len(features),
                    "max_depth": depth,
                    "min_leaf": min_leaf,
                    "auc": metrics["auc"],
                    "balanced_accuracy_0p5": metrics["balanced_accuracy"],
                    "accuracy_0p5": metrics["accuracy"],
                    "encoded_feature_count": len(encoder.encoded_names),
                    "raw_features": features,
                })
    results.sort(
        key=lambda r: (
            r["auc"] if r["auc"] is not None else -1.0,
            r["balanced_accuracy_0p5"] if r["balanced_accuracy_0p5"] is not None else -1.0,
            -r["top_k"],
        ),
        reverse=True,
    )
    return {
        "selected": results[0],
        "top_grid": results[:12],
    }


def analyze_forest_variant(
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    splits = split_rows(rows)
    search = select_forest_hyperparams(
        splits["inner_train"],
        splits["inner_val"],
        features,
        types,
    )
    selected = search["selected"]
    chosen_features = list(selected["raw_features"])

    model, encoder, val_probs = train_forest(
        splits["dev"],
        splits["outer_val"],
        chosen_features,
        types,
        max_depth=int(selected["max_depth"]),
        min_leaf=int(selected["min_leaf"]),
    )
    y_val = [label(r) for r in splits["outer_val"]]
    val_binary = binary_metrics(y_val, val_probs)
    triage = choose_triage_thresholds(y_val, val_probs)

    test_probs = model.predict_proba(encoder.transform(splits["test"]))
    y_test = [label(r) for r in splits["test"]]
    test_binary = binary_metrics(y_test, test_probs)
    selected_triage = triage["selected"]
    test_triage = None
    if selected_triage is not None:
        test_triage = triage_metrics(
            y_test,
            test_probs,
            float(selected_triage["lower"]),
            float(selected_triage["upper"]),
        )

    seen_symbols = {r["meta_symbol"] for r in splits["dev_plus_val"]}
    novel_indices = [
        i for i, row in enumerate(splits["test"])
        if row["meta_symbol"] not in seen_symbols
    ]
    novel_binary = None
    novel_triage = None
    if novel_indices:
        ny = [y_test[i] for i in novel_indices]
        np = [test_probs[i] for i in novel_indices]
        novel_binary = binary_metrics(ny, np)
        if selected_triage is not None:
            novel_triage = triage_metrics(
                ny, np,
                float(selected_triage["lower"]),
                float(selected_triage["upper"]),
            )

    return {
        "model_type": "shallow_random_forest",
        "hyperparameter_search": {
            "selected": {
                k: v for k, v in selected.items() if k != "raw_features"
            },
            "selected_raw_features": chosen_features,
            "top_grid": [
                {k: v for k, v in item.items() if k != "raw_features"}
                for item in search["top_grid"]
            ],
        },
        "outer_validation": {
            "binary_0p5": val_binary,
            "triage_selection": triage,
        },
        "final_test": {
            "binary_0p5": test_binary,
            "triage": test_triage,
            "novel_symbol_n": len(novel_indices),
            "novel_symbol_binary_0p5": novel_binary,
            "novel_symbol_triage": novel_triage,
        },
        "encoded_feature_count": len(encoder.encoded_names),
    }



def select_stable_features(
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
    min_block_separation: float = 0.05,
) -> dict[str, Any]:
    splits = split_rows(rows)
    dev = splits["dev"]
    n = len(dev)
    parts = [
        dev[i * n // 3:(i + 1) * n // 3]
        for i in range(3)
    ]
    selected = []
    diagnostics = []
    for feature in features:
        scores = []
        directions = []
        for part in parts:
            if types[feature] == "numeric":
                info = numeric_separation(part, feature)
                directions.append(info["direction"])
            else:
                info = categorical_separation(part, feature)
            scores.append(info["score"])
        nonzero = [d for d in directions if d != 0]
        sign_ok = len(set(nonzero)) <= 1 if nonzero else True
        keep = min(scores) >= min_block_separation and sign_ok
        diagnostics.append({
            "feature": feature,
            "type": types[feature],
            "block_scores": scores,
            "min_score": min(scores),
            "median_score": statistics.median(scores),
            "numeric_direction_consistent": sign_ok,
            "selected": keep,
        })
        if keep:
            selected.append((
                statistics.median(scores),
                min(scores),
                feature,
            ))
    selected.sort(reverse=True)
    return {
        "min_block_separation": min_block_separation,
        "selected_features": [x[2] for x in selected],
        "selected_count": len(selected),
        "diagnostics": sorted(
            diagnostics,
            key=lambda x: (x["median_score"], x["min_score"]),
            reverse=True,
        ),
    }


def analyze_stability_selected(
    rows: list[dict[str, str]],
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    selection = select_stable_features(rows, features, types)
    stable = list(selection["selected_features"])
    splits = split_rows(rows)

    def evaluate(kind: str) -> dict[str, Any]:
        if kind == "logistic":
            model, encoder, val_probs = train_model(
                splits["dev"],
                splits["outer_val"],
                stable,
                types,
                4.0,
            )
        else:
            model, encoder, val_probs = train_forest(
                splits["dev"],
                splits["outer_val"],
                stable,
                types,
                3,
                25,
            )
        y_val = [label(r) for r in splits["outer_val"]]
        val_binary = binary_metrics(y_val, val_probs)
        triage = choose_triage_thresholds(y_val, val_probs)

        test_probs = model.predict_proba(encoder.transform(splits["test"]))
        y_test = [label(r) for r in splits["test"]]
        test_binary = binary_metrics(y_test, test_probs)
        selected_triage = triage["selected"]
        test_triage = None
        if selected_triage is not None:
            test_triage = triage_metrics(
                y_test,
                test_probs,
                float(selected_triage["lower"]),
                float(selected_triage["upper"]),
            )

        seen_symbols = {r["meta_symbol"] for r in splits["dev_plus_val"]}
        novel_indices = [
            i for i, row in enumerate(splits["test"])
            if row["meta_symbol"] not in seen_symbols
        ]
        novel_y = [y_test[i] for i in novel_indices]
        novel_p = [test_probs[i] for i in novel_indices]
        novel_binary = binary_metrics(novel_y, novel_p) if novel_indices else None
        novel_triage = None
        if novel_indices and selected_triage is not None:
            novel_triage = triage_metrics(
                novel_y,
                novel_p,
                float(selected_triage["lower"]),
                float(selected_triage["upper"]),
            )
        return {
            "kind": kind,
            "encoded_feature_count": len(encoder.encoded_names),
            "outer_binary": val_binary,
            "outer_triage_selection": triage,
            "test_binary": test_binary,
            "test_triage": test_triage,
            "novel_symbol_n": len(novel_indices),
            "novel_binary": novel_binary,
            "novel_triage": novel_triage,
        }

    return {
        "selection": selection,
        "logistic": evaluate("logistic"),
        "forest": evaluate("forest"),
    }


def entry_information_diagnostics(
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    def zero_rate(feature: str) -> dict[str, Any]:
        values = [float(r[feature]) for r in rows]
        n0 = sum(v == 0.0 for v in values)
        return {
            "zero_n": n0,
            "n": len(values),
            "zero_pct": 100.0 * n0 / len(values),
        }

    return {
        "opposite_score": zero_rate("f_opposite_score"),
        "opposite_momentum_component": zero_rate(
            "f_score_component_opposite_momentum"
        ),
        "opposite_activity_component": zero_rate(
            "f_score_component_opposite_activity"
        ),
        "opposite_persistence_component": zero_rate(
            "f_score_component_opposite_persistence"
        ),
        "opposite_timeframe_consistency_component": zero_rate(
            "f_score_component_opposite_timeframe_consistency"
        ),
        "stage11c_price_family_counts": dict(
            Counter(r["f_gate_price_family"] for r in rows)
        ),
        "stage11c_ret3_aligned_counts": dict(
            Counter(r["f_gate_ret3_aligned"] for r in rows)
        ),
        "stage11c_ret3_opposite_counts": dict(
            Counter(r["f_gate_ret3_opposite"] for r in rows)
        ),
        "stage11c_opposite_micro_structure_counts": dict(
            Counter(r["f_gate_opposite_micro_structure"] for r in rows)
        ),
        "interpretation": (
            "Current admitted-entry feature space is strongly conditioned on "
            "the already-selected side and carries little independent opposite-"
            "thesis evidence."
        ),
    }


def wd5b_conclusion(
    variant_results: dict[str, Any],
    nonlinear: dict[str, Any],
    stability_selected: dict[str, Any],
) -> dict[str, Any]:
    outer_aucs = {
        "portable_logistic": variant_results["portable_market"]
            ["outer_validation"]["binary_0p5"]["auc"],
        "full_causal_logistic": variant_results["full_causal_sensitivity"]
            ["outer_validation"]["binary_0p5"]["auc"],
        "portable_forest": nonlinear["outer_validation"]
            ["binary_0p5"]["auc"],
        "stable_logistic": stability_selected["logistic"]
            ["outer_binary"]["auc"],
        "stable_forest": stability_selected["forest"]
            ["outer_binary"]["auc"],
    }
    max_outer_auc = max(float(v) for v in outer_aucs.values() if v is not None)
    floors = {
        "portable_logistic": variant_results["portable_market"]
            ["outer_validation"]["triage_selection"]["selected_precision_floor"],
        "full_causal_logistic": variant_results["full_causal_sensitivity"]
            ["outer_validation"]["triage_selection"]["selected_precision_floor"],
        "portable_forest": nonlinear["outer_validation"]
            ["triage_selection"]["selected_precision_floor"],
        "stable_logistic": stability_selected["logistic"]
            ["outer_triage_selection"]["selected_precision_floor"],
        "stable_forest": stability_selected["forest"]
            ["outer_triage_selection"]["selected_precision_floor"],
    }
    any_floor_060 = any(
        floor is not None and float(floor) >= 0.60
        for floor in floors.values()
    )
    status = (
        "ROBUST_SIGNAL_FOUND"
        if max_outer_auc >= 0.60 and any_floor_060
        else "NO_ROBUST_PREENTRY_DISCRIMINATOR"
    )
    return {
        "status": status,
        "outer_validation_auc_by_model": outer_aucs,
        "max_outer_validation_auc": max_outer_auc,
        "both_action_precision_floor_by_model": floors,
        "any_model_achieved_both_action_precision_floor_0p60": any_floor_060,
        "final_test_is_not_used_to_override_outer_validation_failure": True,
    }

def run_wd5b() -> dict[str, Any]:
    rows, manifest = load_rows()
    types = feature_types(manifest)
    variants = feature_variants(manifest)
    splits = split_rows(rows)

    stability = feature_stability(
        rows,
        variants["portable_market"],
        types,
    )

    variant_results = {
        name: analyze_variant(name, rows, features, types)
        for name, features in variants.items()
    }
    nonlinear_portable = analyze_forest_variant(
        rows,
        variants["portable_market"],
        types,
    )
    stability_selected = analyze_stability_selected(
        rows,
        variants["portable_market"],
        types,
    )
    information_diagnostics = entry_information_diagnostics(rows)
    conclusion = wd5b_conclusion(
        variant_results,
        nonlinear_portable,
        stability_selected,
    )

    class_by_split = {}
    for name, part in splits.items():
        class_by_split[name] = {
            "n": len(part),
            "reverse": sum(label(r) for r in part),
            "no_trade": len(part) - sum(label(r) for r in part),
            "opened_min_ms": min(int(r["meta_opened_at_ms"]) for r in part),
            "opened_max_ms": max(int(r["meta_opened_at_ms"]) for r in part),
        }

    result = {
        "version": WD5B_VERSION,
        "authority": "RESEARCH_ONLY",
        "objective": (
            "Causally distinguish OPPOSITE_FROM_ENTRY_WIN from "
            "NO_TRADE_TARGET before entry."
        ),
        "rows": len(rows),
        "class_counts": dict(Counter(r["target_strict_1_to_1"] for r in rows)),
        "split_design": {
            "inner_train": "first 40% chronological; feature/hyperparameter selection",
            "inner_val": "next 20%; hyperparameter selection only",
            "outer_val": "next 20%; threshold selection only",
            "final_test": "last 20%; untouched until model and thresholds fixed",
            "class_by_split": class_by_split,
        },
        "feature_stability_portable_market": stability,
        "variants": variant_results,
        "nonlinear_portable": nonlinear_portable,
        "stability_selected_portable": stability_selected,
        "entry_information_diagnostics": information_diagnostics,
        "conclusion": conclusion,
        "notes": {
            "primary_variant": "portable_market",
            "full_causal_sensitivity": (
                "Includes time-of-day, processing latency, and raw scale proxy "
                "features. It is reported only as sensitivity, not the primary "
                "portable discriminator."
            ),
            "flip_classes": (
                "14 FLIP_1M_WIN and 14 FLIP_3M_WIN excluded from primary binary "
                "discovery and reserved for a later secondary classifier."
            ),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
