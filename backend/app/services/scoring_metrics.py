from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional


METRIC_VERSION = "precision-recall-v2"
TEXT_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+", re.IGNORECASE)


@dataclass
class NormalizedUnit:
    key: str
    canonical: str
    summary: str
    tokens: set[str]


@dataclass
class ParsedScoringInput:
    units: list[NormalizedUnit]
    parse_status: str
    raw_text: str


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    cleaned = re.sub(r"[，,。；;：:、|]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_json_candidate(text: str) -> Optional[str]:
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if cleaned.startswith("{") or cleaned.startswith("["):
        return cleaned
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    return match.group(1) if match else None


def _canonicalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        parts = [_canonicalize_value(item) for item in value]
        normalized = sorted(part for part in parts if part)
        return "|".join(normalized)
    if isinstance(value, dict):
        normalized_items: list[str] = []
        for key in sorted(value.keys()):
            item_value = _canonicalize_value(value[key])
            if item_value:
                normalized_items.append(f"{_normalize_text(str(key))}={item_value}")
        return ";".join(normalized_items)
    return _normalize_text(str(value))


def _build_tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in TEXT_TOKEN_PATTERN.findall(value):
            normalized = _normalize_text(token)
            if normalized:
                tokens.add(normalized)
    return tokens


def _summarize_dict_unit(value: dict[str, Any]) -> tuple[str, str, str]:
    explicit_key = ""
    for key_name in ("key", "event_id", "id"):
        raw = value.get(key_name)
        if isinstance(raw, str) and raw.strip():
            explicit_key = _normalize_text(raw)
            break

    canonical = _canonicalize_value(value)
    summary_parts = []
    for field in ("title", "description", "subject", "action", "label", "name"):
        raw = value.get(field)
        if isinstance(raw, str) and raw.strip():
            summary_parts.append(raw.strip())
    summary = " / ".join(summary_parts[:3]) or canonical or "{}"
    return explicit_key or canonical, canonical, summary


def _to_units_from_json(value: Any) -> list[NormalizedUnit]:
    if isinstance(value, dict):
        event_list = value.get("event") or value.get("events")
        if isinstance(event_list, list):
            return _to_units_from_json(event_list)
        key, canonical, summary = _summarize_dict_unit(value)
        if not canonical:
            return []
        return [NormalizedUnit(key=key, canonical=canonical, summary=summary, tokens=_build_tokens(key, canonical, summary))]

    if isinstance(value, list):
        units: list[NormalizedUnit] = []
        for item in value:
            units.extend(_to_units_from_json(item))
        return units

    if isinstance(value, str):
        return _split_text_units(value, parse_status="fallback_parsed").units

    canonical = _canonicalize_value(value)
    if not canonical:
        return []
    return [NormalizedUnit(key=canonical, canonical=canonical, summary=canonical, tokens=_build_tokens(canonical))]


def _split_text_units(text: str, parse_status: str) -> ParsedScoringInput:
    normalized = text.strip()
    if not normalized:
        return ParsedScoringInput(units=[], parse_status=parse_status, raw_text=text)

    segments = [
        _normalize_text(part)
        for part in re.split(r"[\n\r]+|[。！？!?；;]", normalized)
    ]
    units: list[NormalizedUnit] = []
    for segment in segments:
        if not segment or len(segment) < 2:
            continue
        units.append(
            NormalizedUnit(
                key=segment,
                canonical=segment,
                summary=segment,
                tokens=_build_tokens(segment),
            )
        )
    return ParsedScoringInput(units=units, parse_status=parse_status, raw_text=text)


def parse_scoring_input(text: str) -> ParsedScoringInput:
    raw_text = text or ""
    stripped = raw_text.strip()
    if not stripped:
        return ParsedScoringInput(units=[], parse_status="parsed", raw_text=raw_text)

    candidate = _extract_json_candidate(stripped)
    if candidate:
        try:
            parsed = json.loads(candidate)
            units = _to_units_from_json(parsed)
            return ParsedScoringInput(units=units, parse_status="parsed", raw_text=raw_text)
        except json.JSONDecodeError:
            pass

    return _split_text_units(raw_text, parse_status="fallback_parsed")


def _calculate_match_score(left: NormalizedUnit, right: NormalizedUnit) -> float:
    if left.key and left.key == right.key:
        return 1.0
    if left.canonical and left.canonical == right.canonical:
        return 0.95
    if not left.tokens or not right.tokens:
        return 0.0
    overlap = len(left.tokens & right.tokens)
    if overlap == 0:
        return 0.0
    union = len(left.tokens | right.tokens)
    return overlap / union


def _match_units(ground_truth_units: list[NormalizedUnit], predicted_units: list[NormalizedUnit]) -> tuple[int, list[tuple[NormalizedUnit, NormalizedUnit]], list[NormalizedUnit], list[NormalizedUnit]]:
    unmatched_predictions = list(predicted_units)
    matched_pairs: list[tuple[NormalizedUnit, NormalizedUnit]] = []
    missed_units: list[NormalizedUnit] = []

    for gt_unit in ground_truth_units:
        best_index = -1
        best_score = 0.0
        for index, predicted_unit in enumerate(unmatched_predictions):
            score = _calculate_match_score(gt_unit, predicted_unit)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index >= 0 and best_score >= 0.6:
            matched_pairs.append((gt_unit, unmatched_predictions.pop(best_index)))
        else:
            missed_units.append(gt_unit)

    false_positive_units = unmatched_predictions
    return len(matched_pairs), matched_pairs, missed_units, false_positive_units


def _format_reason(
    parse_statuses: tuple[str, str],
    matched_pairs: list[tuple[NormalizedUnit, NormalizedUnit]],
    missed_units: list[NormalizedUnit],
    false_positive_units: list[NormalizedUnit],
    is_empty_sample: bool,
    empty_sample_passed: bool,
) -> str:
    gt_status, pred_status = parse_statuses
    if is_empty_sample:
        return "标注结果和模型输出都没有可评测单元，记为空样本正确，不参与主指标聚合。"

    parts = [f"解析状态: GT={gt_status}, 预测={pred_status}。"]
    if matched_pairs:
        matched_summary = "；".join(f"{gt.summary} <- {pred.summary}" for gt, pred in matched_pairs[:3])
        parts.append(f"命中 {len(matched_pairs)} 项: {matched_summary}。")
    else:
        parts.append("未命中任何标注项。")

    if missed_units:
        missed_summary = "；".join(unit.summary for unit in missed_units[:3])
        parts.append(f"漏检 {len(missed_units)} 项: {missed_summary}。")
    if false_positive_units:
        fp_summary = "；".join(unit.summary for unit in false_positive_units[:3])
        parts.append(f"误报 {len(false_positive_units)} 项: {fp_summary}。")
    if empty_sample_passed:
        parts.append("空样本判断正确。")
    return "".join(parts)


def _compute_percentage(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def compute_score_metrics(ground_truth: str, model_output: str) -> dict[str, Any]:
    parsed_ground_truth = parse_scoring_input(ground_truth)
    parsed_model_output = parse_scoring_input(model_output)

    gt_units = parsed_ground_truth.units
    predicted_units = parsed_model_output.units
    is_empty_sample = len(gt_units) == 0 and len(predicted_units) == 0
    empty_sample_passed = is_empty_sample
    is_scorable = True

    matched_count, matched_pairs, missed_units, false_positive_units = _match_units(gt_units, predicted_units)
    fn_count = len(missed_units)
    fp_count = len(false_positive_units)
    tp_count = matched_count

    recall = _compute_percentage(tp_count, tp_count + fn_count)
    precision = _compute_percentage(tp_count, tp_count + fp_count)

    if len(gt_units) == 0 and len(predicted_units) > 0:
        precision = 0.0
        recall = None
    elif len(gt_units) > 0 and len(predicted_units) == 0:
        recall = 0.0
        precision = None
    elif is_empty_sample:
        recall = None
        precision = None

    if recall is None and precision is None:
        score = None
    elif recall is None:
        score = round(precision or 0)
    elif precision is None:
        score = round(recall or 0)
    else:
        score = round((recall + precision) / 2)

    reason = _format_reason(
        (parsed_ground_truth.parse_status, parsed_model_output.parse_status),
        matched_pairs,
        missed_units,
        false_positive_units,
        is_empty_sample,
        empty_sample_passed,
    )

    return {
        "recall": recall,
        "precision": precision,
        "score": score,
        "reason": reason,
        "tp_count": tp_count,
        "fp_count": fp_count,
        "fn_count": fn_count,
        "ground_truth_unit_count": len(gt_units),
        "predicted_unit_count": len(predicted_units),
        "is_scorable": is_scorable,
        "is_empty_sample": is_empty_sample,
        "empty_sample_passed": empty_sample_passed,
        "metric_version": METRIC_VERSION,
        "ground_truth_parse_status": parsed_ground_truth.parse_status,
        "model_output_parse_status": parsed_model_output.parse_status,
    }
