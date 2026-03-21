"""Evaluator — golden set comparison with field-level precision/recall/F1."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from src.models import EvalResult, FieldScore


class Evaluator:
    """Compare extraction results against golden test cases."""

    FUZZY_THRESHOLD = 0.85

    def __init__(self, golden_path: str | Path = "data/golden/test_cases.yaml") -> None:
        self._golden_path = Path(golden_path)
        self._test_cases: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load golden test cases from YAML."""
        if self._golden_path.exists():
            with open(self._golden_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self._test_cases = data.get("test_cases", [])

    @property
    def test_cases(self) -> list[dict[str, Any]]:
        return self._test_cases

    def evaluate_single(
        self,
        case_id: str,
        doc_type: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> EvalResult:
        """Evaluate a single extraction result against expected output."""
        field_scores: list[FieldScore] = []
        all_fields = set(expected.keys()) | set(actual.keys())

        for field in all_fields:
            exp_val = expected.get(field)
            act_val = actual.get(field)

            if field not in actual:
                field_scores.append(FieldScore(
                    field=field,
                    expected=exp_val,
                    actual=None,
                    match=False,
                    match_type="missing",
                ))
            elif field not in expected:
                field_scores.append(FieldScore(
                    field=field,
                    expected=None,
                    actual=act_val,
                    match=False,
                    match_type="extra",
                ))
            elif self._exact_match(exp_val, act_val):
                field_scores.append(FieldScore(
                    field=field,
                    expected=exp_val,
                    actual=act_val,
                    match=True,
                    match_type="exact",
                ))
            elif self._fuzzy_match(exp_val, act_val):
                field_scores.append(FieldScore(
                    field=field,
                    expected=exp_val,
                    actual=act_val,
                    match=True,
                    match_type="fuzzy",
                ))
            else:
                field_scores.append(FieldScore(
                    field=field,
                    expected=exp_val,
                    actual=act_val,
                    match=False,
                    match_type="mismatch",
                ))

        # Calculate precision, recall, F1
        expected_fields = {f for f in all_fields if f in expected}
        actual_fields = {f for f in all_fields if f in actual}
        matched = {s.field for s in field_scores if s.match}

        precision = len(matched) / len(actual_fields) if actual_fields else 0.0
        recall = len(matched) / len(expected_fields) if expected_fields else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return EvalResult(
            case_id=case_id,
            doc_type=doc_type,
            field_scores=field_scores,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
        )

    def _exact_match(self, expected: Any, actual: Any) -> bool:
        """Check for exact match, with type-flexible number comparison."""
        if expected == actual:
            return True
        # Compare numbers flexibly
        try:
            return float(expected) == float(actual)
        except (TypeError, ValueError):
            return False

    def _fuzzy_match(self, expected: Any, actual: Any) -> bool:
        """Check for fuzzy string match using sequence similarity."""
        if not isinstance(expected, str) or not isinstance(actual, str):
            return False
        ratio = SequenceMatcher(None, expected.lower(), actual.lower()).ratio()
        return ratio >= self.FUZZY_THRESHOLD

    def aggregate(self, results: list[EvalResult]) -> dict[str, Any]:
        """Aggregate evaluation results into a summary report."""
        if not results:
            return {"total": 0, "avg_f1": 0.0, "avg_precision": 0.0, "avg_recall": 0.0}

        total = len(results)
        avg_f1 = sum(r.f1 for r in results) / total
        avg_precision = sum(r.precision for r in results) / total
        avg_recall = sum(r.recall for r in results) / total

        by_type: dict[str, list[EvalResult]] = {}
        for r in results:
            by_type.setdefault(r.doc_type, []).append(r)

        per_type = {}
        for dtype, type_results in by_type.items():
            n = len(type_results)
            per_type[dtype] = {
                "count": n,
                "avg_f1": round(sum(r.f1 for r in type_results) / n, 4),
                "avg_precision": round(sum(r.precision for r in type_results) / n, 4),
                "avg_recall": round(sum(r.recall for r in type_results) / n, 4),
            }

        return {
            "total": total,
            "avg_f1": round(avg_f1, 4),
            "avg_precision": round(avg_precision, 4),
            "avg_recall": round(avg_recall, 4),
            "per_type": per_type,
        }
