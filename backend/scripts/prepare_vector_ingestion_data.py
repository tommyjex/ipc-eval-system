from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_ID = 7
DEFAULT_EXPECTED_COUNT = 215
DEFAULT_TRANSLATION_CONCURRENCY = 50
DEFAULT_TRANSLATION_MODEL = "doubao-seed-2-0-pro-260215"
CHINESE_TEXT_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class PreparationError(RuntimeError):
    """向量库入库数据准备失败。"""


class TranslationError(PreparationError):
    """翻译单个 JSON 字符串值失败。"""


class Translator(Protocol):
    def translate(self, text: str) -> str:
        """将中文文本翻译为英文。"""


@dataclass(frozen=True)
class SourceAnnotationRecord:
    data_id: int
    file_name: str
    file_type: str | None
    file_size: int | None
    tos_key: str
    tos_bucket: str
    annotation_id: int
    ground_truth: str


@dataclass(frozen=True)
class TranslationStats:
    total_strings: int = 0
    translated_strings: int = 0

    def plus(self, other: "TranslationStats") -> "TranslationStats":
        return TranslationStats(
            total_strings=self.total_strings + other.total_strings,
            translated_strings=self.translated_strings + other.translated_strings,
        )


@dataclass(frozen=True)
class TranslationWorkItem:
    record_index: int
    data_id: int
    path: str
    text: str


@dataclass(frozen=True)
class PreparationResult:
    output_path: Path | None
    record_count: int
    translation_stats: TranslationStats
    dry_run: bool


class ArkTextTranslator:
    def __init__(self, model: str | None = None):
        from app.services.ark_client import get_ark_client

        self._client = get_ark_client()
        self._model = model or DEFAULT_TRANSLATION_MODEL

    def translate(self, text: str) -> str:
        prompt = (
            "Translate the following Chinese text into natural English.\n"
            "Keep numbers, names, punctuation meaning, and formatting as much as possible.\n"
            "Return only the translated English text, with no quotes and no explanation.\n\n"
            f"Text:\n{text}"
        )
        result = self._client.annotate(
            [{"type": "input_text", "text": prompt}],
            model=self._model,
        )
        translated = result.strip()
        if not translated:
            raise TranslationError("翻译结果为空")
        return translated


class MockTranslator:
    def translate(self, text: str) -> str:
        return f"[EN]{text}"


def contains_chinese(text: str) -> bool:
    return bool(CHINESE_TEXT_PATTERN.search(text))


def translate_json_value(
    value: Any,
    translator: Translator,
    *,
    data_id: int,
    path: str = "$",
) -> tuple[Any, TranslationStats]:
    if isinstance(value, dict):
        translated_items: dict[str, Any] = {}
        stats = TranslationStats()
        for key, child in value.items():
            translated_child, child_stats = translate_json_value(
                child,
                translator,
                data_id=data_id,
                path=f"{path}.{key}",
            )
            translated_items[key] = translated_child
            stats = stats.plus(child_stats)
        return translated_items, stats

    if isinstance(value, list):
        translated_list: list[Any] = []
        stats = TranslationStats()
        for index, child in enumerate(value):
            translated_child, child_stats = translate_json_value(
                child,
                translator,
                data_id=data_id,
                path=f"{path}[{index}]",
            )
            translated_list.append(translated_child)
            stats = stats.plus(child_stats)
        return translated_list, stats

    if isinstance(value, str):
        if not contains_chinese(value):
            return value, TranslationStats(total_strings=1, translated_strings=0)
        try:
            translated = translator.translate(value)
        except Exception as exc:
            raise TranslationError(
                f"data_id={data_id}, path={path}, reason={exc}"
            ) from exc
        return translated, TranslationStats(total_strings=1, translated_strings=1)

    return value, TranslationStats()


def collect_translation_work_items(
    value: Any,
    *,
    data_id: int,
    record_index: int,
    path: str = "$",
) -> tuple[list[TranslationWorkItem], TranslationStats]:
    if isinstance(value, dict):
        work_items: list[TranslationWorkItem] = []
        stats = TranslationStats()
        for key, child in value.items():
            child_work_items, child_stats = collect_translation_work_items(
                child,
                data_id=data_id,
                record_index=record_index,
                path=f"{path}.{key}",
            )
            work_items.extend(child_work_items)
            stats = stats.plus(child_stats)
        return work_items, stats

    if isinstance(value, list):
        work_items = []
        stats = TranslationStats()
        for index, child in enumerate(value):
            child_work_items, child_stats = collect_translation_work_items(
                child,
                data_id=data_id,
                record_index=record_index,
                path=f"{path}[{index}]",
            )
            work_items.extend(child_work_items)
            stats = stats.plus(child_stats)
        return work_items, stats

    if isinstance(value, str):
        if not contains_chinese(value):
            return [], TranslationStats(total_strings=1, translated_strings=0)
        return (
            [
                TranslationWorkItem(
                    record_index=record_index,
                    data_id=data_id,
                    path=path,
                    text=value,
                )
            ],
            TranslationStats(total_strings=1, translated_strings=1),
        )

    return [], TranslationStats()


def translate_work_items_concurrently(
    work_items: list[TranslationWorkItem],
    translator: Translator,
    *,
    concurrency: int,
) -> dict[tuple[int, str], str]:
    if concurrency < 1:
        raise PreparationError("并发数必须大于等于 1")
    if not work_items:
        return {}

    translations: dict[tuple[int, str], str] = {}
    max_workers = min(concurrency, len(work_items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(translator.translate, item.text): item for item in work_items
        }
        completed = 0
        total = len(work_items)
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                translated = future.result().strip()
            except Exception as exc:
                raise TranslationError(
                    f"data_id={item.data_id}, path={item.path}, reason={exc}"
                ) from exc
            if not translated:
                raise TranslationError(
                    f"data_id={item.data_id}, path={item.path}, reason=翻译结果为空"
                )
            translations[(item.record_index, item.path)] = translated
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"翻译进度: {completed}/{total}")
    return translations


def apply_translations(
    value: Any,
    translations: dict[tuple[int, str], str],
    *,
    record_index: int,
    path: str = "$",
) -> Any:
    if isinstance(value, dict):
        return {
            key: apply_translations(
                child,
                translations,
                record_index=record_index,
                path=f"{path}.{key}",
            )
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [
            apply_translations(
                child,
                translations,
                record_index=record_index,
                path=f"{path}[{index}]",
            )
            for index, child in enumerate(value)
        ]

    if isinstance(value, str):
        return translations.get((record_index, path), value)

    return value


def parse_annotation_json(record: SourceAnnotationRecord) -> Any:
    try:
        return json.loads(record.ground_truth)
    except json.JSONDecodeError as exc:
        raise PreparationError(
            f"标注 JSON 解析失败: data_id={record.data_id}, reason={exc.msg}"
        ) from exc


def build_output_record(
    record: SourceAnnotationRecord,
    translator: Translator,
) -> tuple[dict[str, Any], TranslationStats]:
    original_annotation = parse_annotation_json(record)
    english_annotation, stats = translate_json_value(
        original_annotation,
        translator,
        data_id=record.data_id,
    )
    return (
        {
            "data_id": record.data_id,
            "file_name": record.file_name,
            "file_type": record.file_type,
            "file_size": record.file_size,
            "tos": {
                "bucket": record.tos_bucket,
                "key": record.tos_key,
            },
            "annotation_id": record.annotation_id,
            "original_annotation": original_annotation,
            "english_annotation": english_annotation,
        },
        stats,
    )


def fetch_source_records(dataset_id: int = DEFAULT_DATASET_ID) -> list[SourceAnnotationRecord]:
    from app.core.database import SessionLocal
    from app.models import Annotation, EvaluationData

    db = SessionLocal()
    try:
        rows = (
            db.query(EvaluationData, Annotation)
            .join(Annotation, Annotation.data_id == EvaluationData.id)
            .filter(EvaluationData.dataset_id == dataset_id)
            .filter(Annotation.ground_truth.isnot(None))
            .filter(Annotation.ground_truth != "")
            .order_by(EvaluationData.id.asc(), Annotation.created_at.desc(), Annotation.id.desc())
            .all()
        )
    finally:
        db.close()

    records_by_data_id: dict[int, SourceAnnotationRecord] = {}
    for data, annotation in rows:
        if data.id in records_by_data_id:
            continue
        records_by_data_id[data.id] = SourceAnnotationRecord(
            data_id=int(data.id),
            file_name=data.file_name,
            file_type=data.file_type,
            file_size=int(data.file_size) if data.file_size is not None else None,
            tos_key=data.tos_key,
            tos_bucket=data.tos_bucket,
            annotation_id=int(annotation.id),
            ground_truth=annotation.ground_truth,
        )

    return list(records_by_data_id.values())


def validate_record_count(records: list[SourceAnnotationRecord], expected_count: int) -> None:
    actual_count = len(records)
    if actual_count != expected_count:
        raise PreparationError(
            f"可处理标注数据数量不符合预期: actual={actual_count}, expected={expected_count}"
        )


def write_json_atomically(output_path: Path, payload: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
        os.replace(temp_path, output_path)
    except Exception:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        raise


def validate_output_file(output_path: Path, expected_count: int) -> None:
    try:
        with output_path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except Exception as exc:
        raise PreparationError(f"输出文件不是合法 JSON: path={output_path}, reason={exc}") from exc

    if not isinstance(payload, list):
        raise PreparationError(f"输出文件顶层结构必须为数组: path={output_path}")

    actual_count = len(payload)
    if actual_count != expected_count:
        raise PreparationError(
            f"输出文件记录数量不符合预期: actual={actual_count}, expected={expected_count}"
        )


def prepare_vector_ingestion_data(
    records: list[SourceAnnotationRecord],
    translator: Translator,
    *,
    output_path: Path | None,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
    overwrite: bool = False,
    dry_run: bool = False,
    concurrency: int = DEFAULT_TRANSLATION_CONCURRENCY,
) -> PreparationResult:
    validate_record_count(records, expected_count)
    if not dry_run:
        if output_path is None:
            raise PreparationError("必须通过 --output 指定输出文件路径")
        if output_path.exists() and not overwrite:
            raise PreparationError(f"输出文件已存在，请添加 --overwrite 后重试: {output_path}")

    parsed_annotations: list[Any] = []
    all_work_items: list[TranslationWorkItem] = []
    total_stats = TranslationStats()
    for record_index, record in enumerate(records):
        original_annotation = parse_annotation_json(record)
        work_items, stats = collect_translation_work_items(
            original_annotation,
            data_id=record.data_id,
            record_index=record_index,
        )
        parsed_annotations.append(original_annotation)
        all_work_items.extend(work_items)
        total_stats = total_stats.plus(stats)

    print(
        f"开始翻译: 记录数={len(records)}, "
        f"字符串总数={total_stats.total_strings}, "
        f"待翻译字符串数={len(all_work_items)}, 并发={concurrency}"
    )
    translations = translate_work_items_concurrently(
        all_work_items,
        translator,
        concurrency=concurrency,
    )

    output_records: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        original_annotation = parsed_annotations[record_index]
        english_annotation = apply_translations(
            original_annotation,
            translations,
            record_index=record_index,
        )
        output_records.append(
            {
                "data_id": record.data_id,
                "file_name": record.file_name,
                "file_type": record.file_type,
                "file_size": record.file_size,
                "tos": {
                    "bucket": record.tos_bucket,
                    "key": record.tos_key,
                },
                "annotation_id": record.annotation_id,
                "original_annotation": original_annotation,
                "english_annotation": english_annotation,
            }
        )

    if not dry_run and output_path is not None:
        write_json_atomically(output_path, output_records)
        validate_output_file(output_path, expected_count)

    return PreparationResult(
        output_path=output_path if not dry_run else None,
        record_count=len(output_records),
        translation_stats=total_stats,
        dry_run=dry_run,
    )


def build_translator(name: str, model: str | None) -> Translator:
    if name == "mock":
        return MockTranslator()
    if name == "ark":
        return ArkTextTranslator(model=model)
    raise PreparationError(f"不支持的翻译器: {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="准备向量库入库所需的英文标注 JSON 数据。")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件路径。")
    parser.add_argument(
        "--dataset-id",
        type=int,
        default=DEFAULT_DATASET_ID,
        help="评测集 ID，默认 7。",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=DEFAULT_EXPECTED_COUNT,
        help="期望可处理记录数量。",
    )
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件。")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅执行读取、解析和翻译校验，不写入正式输出文件。",
    )
    parser.add_argument(
        "--translator",
        choices=["ark", "mock"],
        default="ark",
        help="翻译器类型；mock 用于本地验证，不调用外部服务。",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_TRANSLATION_MODEL,
        help=f"翻译使用的大模型名称；默认 {DEFAULT_TRANSLATION_MODEL}。",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_TRANSLATION_CONCURRENCY,
        help=f"并发翻译调用数，默认 {DEFAULT_TRANSLATION_CONCURRENCY}。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records = fetch_source_records(dataset_id=args.dataset_id)
        translator = build_translator(args.translator, args.model)
        result = prepare_vector_ingestion_data(
            records,
            translator,
            output_path=args.output,
            expected_count=args.expected_count,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
        )
    except PreparationError as exc:
        print(f"失败: {exc}")
        return 1

    output_text = str(result.output_path) if result.output_path else "(dry-run 未写入)"
    print(f"输出路径: {output_text}")
    print(f"记录数量: {result.record_count}")
    print(f"字符串总数: {result.translation_stats.total_strings}")
    print(f"翻译字符串数: {result.translation_stats.translated_strings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
