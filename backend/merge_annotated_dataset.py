from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT_DIR = Path("../data/annotated")
DEFAULT_OUTPUT_FILE = Path("../data/annotated/drug.jsonl")


def normalize_record(record: dict, source_name: str, line_no: int) -> dict:

    if "text" not in record:
        raise ValueError(f"{source_name} dòng {line_no}: thiếu field 'text'")

    if "labels" not in record and "label" in record:
        record["labels"] = record.pop("label")

    if "labels" not in record:
        record["labels"] = []

    if record["labels"] is None:
        record["labels"] = []

    if not isinstance(record["labels"], list):
        raise ValueError(f"{source_name} dòng {line_no}: field 'labels' phải là list")

    if "meta" not in record or record["meta"] is None:
        record["meta"] = {}

    if not isinstance(record["meta"], dict):
        record["meta"] = {}

    record["meta"].setdefault("source", source_name.replace(".jsonl", ""))

    return record


def iter_jsonl_files(input_dir: Path, output_file: Path) -> list[Path]:
    files = sorted(input_dir.glob("*.jsonl"))

    ignored_names = {
        output_file.name,
        "all_cases.jsonl",
        "train.jsonl",
        "dev.jsonl",
        "val.jsonl",
        "valid.jsonl",
        "test.jsonl",
    }

    files = [p for p in files if p.name not in ignored_names]

    return files


def merge_jsonl(input_dir: Path, output_file: Path) -> None:
    if not input_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục: {input_dir}")

    jsonl_files = iter_jsonl_files(input_dir, output_file)

    if not jsonl_files:
        raise FileNotFoundError(f"Không tìm thấy file .jsonl nào trong: {input_dir}")

    total_records = 0
    total_entities = 0
    label_counts = {}
    file_counts = {}

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="\n") as fout:
        for path in jsonl_files:
            file_records = 0
            file_entities = 0

            with path.open("r", encoding="utf-8") as fin:
                for line_no, line in enumerate(fin, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"{path.name} dòng {line_no}: JSON lỗi: {e}")

                    record = normalize_record(record, path.name, line_no)

                    labels = record.get("labels", [])
                    file_entities += len(labels)

                    for lab in labels:
                        if isinstance(lab, list) and len(lab) >= 3:
                            label_name = lab[2]
                            label_counts[label_name] = label_counts.get(label_name, 0) + 1

                    fout.write(json.dumps(record, ensure_ascii=False) + "\n")

                    file_records += 1
                    total_records += 1

            file_counts[path.name] = {
                "records": file_records,
                "entities": file_entities,
            }
            total_entities += file_entities

    print("\nĐÃ GỘP XONG")
    print(f"Input folder : {input_dir}")
    print(f"Output file  : {output_file}")
    print(f"Số file gộp  : {len(jsonl_files)}")
    print(f"Số records   : {total_records}")
    print(f"Số entities  : {total_entities}")

    print("\nTheo từng file:")
    for name, stats in file_counts.items():
        print(f"  - {name}: {stats['records']} records, {stats['entities']} entities")

    print("\nThống kê nhãn:")
    for label, count in sorted(label_counts.items()):
        print(f"  - {label}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gộp các file JSONL đã annotated thành drug.jsonl"
    )
    parser.add_argument(
        "--input_dir",
        "-i",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Thư mục chứa các file JSONL đã gán nhãn",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="File JSONL đầu ra",
    )

    args = parser.parse_args()

    merge_jsonl(args.input_dir, args.output)


if __name__ == "__main__":
    main()
