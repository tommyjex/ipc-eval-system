import json
from types import SimpleNamespace

import pytest

from scripts.upsert_vector_ingestion_data import (
    UpsertPreparationError,
    build_vikingdb_data_item,
    chunked,
    prepare_and_upsert,
    upsert_data_batches,
)


def _source_record(data_id: int = 1):
    return {
        "data_id": data_id,
        "file_name": "cat.mp4",
        "english_annotation": {
            "description": "A cat is drinking water.",
            "title": "Cat Drinking",
            "event": ["cat", "drink water"],
        },
    }


def test_build_vikingdb_data_item_maps_required_fields():
    item = build_vikingdb_data_item(_source_record(), primary_key_field="id")

    assert item == {
        "id": "1",
        "description": "A cat is drinking water.",
        "title": "Cat Drinking",
        "event": "cat;drink water",
        "des": "A cat is drinking water.;Cat Drinking;cat;drink water",
        "name": "cat.mp4",
    }


def test_build_vikingdb_data_item_supports_custom_primary_key_field():
    item = build_vikingdb_data_item(_source_record(22), primary_key_field="data_id")

    assert item["data_id"] == "22"


def test_build_vikingdb_data_item_requires_annotation_object():
    with pytest.raises(UpsertPreparationError, match="english_annotation"):
        build_vikingdb_data_item({"data_id": 1, "file_name": "a.mp4"})


def test_chunked_limits_batch_size_to_100():
    data = [{"id": str(index)} for index in range(215)]

    batches = list(chunked(data, 100))

    assert [len(batch) for batch in batches] == [100, 100, 15]


class FakeCollectionClient:
    def __init__(self):
        self.requests = []

    def upsert(self, request):
        self.requests.append(request)
        return SimpleNamespace(code="Success", message="")


def test_upsert_data_batches_uses_sdk_request_and_batches():
    data = [{"id": str(index), "name": f"{index}.mp4"} for index in range(205)]
    client = FakeCollectionClient()

    batch_count = upsert_data_batches(data, client, batch_size=100, async_write=True)

    assert batch_count == 3
    assert [len(request.data) for request in client.requests] == [100, 100, 5]
    assert all(request.async_write is True for request in client.requests)


def test_prepare_and_upsert_dry_run_reads_file_and_does_not_upsert(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps([_source_record()], ensure_ascii=False), encoding="utf-8")

    summary = prepare_and_upsert(
        input_path=input_path,
        dry_run=True,
        batch_size=100,
        async_write=False,
        primary_key_field="id",
    )

    assert summary.total_count == 1
    assert summary.batch_count == 1
    assert summary.dry_run is True
