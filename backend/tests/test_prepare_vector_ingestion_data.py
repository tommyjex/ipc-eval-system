import json

import pytest

from scripts.prepare_vector_ingestion_data import (
    PreparationError,
    SourceAnnotationRecord,
    TranslationError,
    contains_chinese,
    prepare_vector_ingestion_data,
    translate_json_value,
)


class MappingTranslator:
    def __init__(self, mapping: dict[str, str] | None = None, fail_on: str | None = None):
        self.mapping = mapping or {}
        self.fail_on = fail_on
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        if self.fail_on == text:
            raise RuntimeError("boom")
        return self.mapping.get(text, f"EN:{text}")


def _record(data_id: int, ground_truth: str) -> SourceAnnotationRecord:
    return SourceAnnotationRecord(
        data_id=data_id,
        file_name=f"{data_id}.jpg",
        file_type="jpg",
        file_size=1024,
        tos_key=f"dataset/7/{data_id}.jpg",
        tos_bucket="bucket",
        annotation_id=data_id + 1000,
        ground_truth=ground_truth,
    )


def test_contains_chinese_detects_cjk_text_only():
    assert contains_chinese("猫在沙发上")
    assert contains_chinese("cat 猫")
    assert not contains_chinese("cat on sofa")
    assert not contains_chinese("123, true, null")


def test_translate_json_value_preserves_structure_and_only_translates_string_values():
    value = {
        "title": "猫咪进食",
        "event": [
            {"subject": "猫", "score": 1, "active": True, "empty": None},
            "already English",
        ],
        "中文字段名": "值",
    }
    translator = MappingTranslator(
        {
            "猫咪进食": "Cat Eating",
            "猫": "cat",
            "值": "value",
        }
    )

    translated, stats = translate_json_value(value, translator, data_id=1)

    assert list(translated.keys()) == ["title", "event", "中文字段名"]
    assert translated["title"] == "Cat Eating"
    assert translated["event"][0] == {"subject": "cat", "score": 1, "active": True, "empty": None}
    assert translated["event"][1] == "already English"
    assert translated["中文字段名"] == "value"
    assert translator.calls == ["猫咪进食", "猫", "值"]
    assert stats.total_strings == 4
    assert stats.translated_strings == 3


def test_translate_json_value_reports_data_id_path_and_reason_on_translation_failure():
    translator = MappingTranslator(fail_on="猫")

    with pytest.raises(TranslationError, match=r"data_id=9, path=\$\.event\[0\]\.subject"):
        translate_json_value({"event": [{"subject": "猫"}]}, translator, data_id=9)


def test_prepare_vector_ingestion_data_fails_on_invalid_json_without_output(tmp_path):
    output_path = tmp_path / "output.json"

    with pytest.raises(PreparationError, match="data_id=1"):
        prepare_vector_ingestion_data(
            [_record(1, '{"title": "猫"')],
            MappingTranslator(),
            output_path=output_path,
            expected_count=1,
            overwrite=True,
        )

    assert not output_path.exists()


def test_prepare_vector_ingestion_data_fails_on_count_mismatch_without_output(tmp_path):
    output_path = tmp_path / "output.json"

    with pytest.raises(PreparationError, match="actual=1, expected=215"):
        prepare_vector_ingestion_data(
            [_record(1, '{"title": "猫"}')],
            MappingTranslator(),
            output_path=output_path,
            expected_count=215,
            overwrite=True,
        )

    assert not output_path.exists()


def test_prepare_vector_ingestion_data_writes_215_records_with_mock_translator(tmp_path):
    output_path = tmp_path / "vector_ingestion.json"
    records = [
        _record(index, json.dumps({"title": "猫", "index": index}, ensure_ascii=False))
        for index in range(215)
    ]

    result = prepare_vector_ingestion_data(
        records,
        MappingTranslator({"猫": "cat"}),
        output_path=output_path,
        expected_count=215,
        overwrite=False,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.record_count == 215
    assert result.translation_stats.translated_strings == 215
    assert len(payload) == 215
    assert payload[0]["data_id"] == 0
    assert payload[0]["file_name"] == "0.jpg"
    assert payload[0]["tos"] == {"bucket": "bucket", "key": "dataset/7/0.jpg"}
    assert payload[0]["original_annotation"] == {"title": "猫", "index": 0}
    assert payload[0]["english_annotation"] == {"title": "cat", "index": 0}


def test_prepare_vector_ingestion_data_dry_run_does_not_write_output(tmp_path):
    output_path = tmp_path / "dry_run.json"

    result = prepare_vector_ingestion_data(
        [_record(1, '{"title": "猫"}')],
        MappingTranslator({"猫": "cat"}),
        output_path=output_path,
        expected_count=1,
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.output_path is None
    assert result.record_count == 1
    assert not output_path.exists()


def test_prepare_vector_ingestion_data_requires_overwrite_for_existing_output(tmp_path):
    output_path = tmp_path / "existing.json"
    output_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(PreparationError, match="--overwrite"):
        prepare_vector_ingestion_data(
            [_record(1, '{"title": "猫"}')],
            MappingTranslator({"猫": "cat"}),
            output_path=output_path,
            expected_count=1,
        )

    assert output_path.read_text(encoding="utf-8") == "[]\n"
