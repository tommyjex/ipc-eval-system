from app.services.scoring_metrics import METRIC_VERSION, compute_score_metrics


def test_compute_score_metrics_for_structured_events():
    ground_truth = """
    {
      "event": [
        {"subject": "person", "action": "fall"},
        {"subject": "car", "action": "stop"}
      ]
    }
    """
    model_output = """
    {
      "event": [
        {"subject": "person", "action": "fall"},
        {"subject": "dog", "action": "bark"}
      ]
    }
    """

    metrics = compute_score_metrics(ground_truth, model_output)

    assert metrics["tp_count"] == 1
    assert metrics["fp_count"] == 1
    assert metrics["fn_count"] == 1
    assert metrics["recall"] == 50.0
    assert metrics["precision"] == 50.0
    assert metrics["score"] == 50
    assert metrics["metric_version"] == METRIC_VERSION


def test_compute_score_metrics_for_empty_sample_with_empty_event_lists():
    metrics = compute_score_metrics('{"event":[]}', '{"event":[]}')

    assert metrics["is_empty_sample"] is True
    assert metrics["empty_sample_passed"] is True
    assert metrics["recall"] is None
    assert metrics["precision"] is None
    assert metrics["score"] is None
    assert "event 列表也为空" in metrics["reason"]


def test_compute_score_metrics_for_empty_ground_truth_with_false_positive_event():
    metrics = compute_score_metrics('{"event":[]}', '{"event":[{"subject":"person","action":"run"}]}')

    assert metrics["tp_count"] == 0
    assert metrics["fp_count"] == 1
    assert metrics["fn_count"] == 0
    assert metrics["is_empty_sample"] is True
    assert metrics["empty_sample_passed"] is False
    assert metrics["recall"] is None
    assert metrics["precision"] == 0.0
    assert "未正确判空" in metrics["reason"]


def test_compute_score_metrics_ignores_description_when_event_is_empty():
    ground_truth = '{"description":"空场景","title":"无人","event":[]}'
    model_output = '{"description":"模型补了描述","title":"依然无人","event":[]}'

    metrics = compute_score_metrics(ground_truth, model_output)

    assert metrics["ground_truth_unit_count"] == 0
    assert metrics["predicted_unit_count"] == 0
    assert metrics["is_empty_sample"] is True
    assert metrics["empty_sample_passed"] is True


def test_compute_score_metrics_for_text_fallback():
    metrics = compute_score_metrics("人员跌倒。车辆逆行。", "人员跌倒。")

    assert metrics["ground_truth_parse_status"] == "fallback_parsed"
    assert metrics["model_output_parse_status"] == "fallback_parsed"
    assert metrics["tp_count"] == 1
    assert metrics["fn_count"] == 1
    assert metrics["fp_count"] == 0
    assert metrics["recall"] == 50.0
    assert metrics["precision"] == 100.0
