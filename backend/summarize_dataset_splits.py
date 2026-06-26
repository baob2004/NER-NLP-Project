# summarize_dataset_splits.py
# Thống kê entity theo split cho file Doccano JSONL.
# Nếu file chưa có split, script sẽ tự chia theo meta.source để tránh cùng 1 bản án rơi vào nhiều tập.

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

DEFAULT_LABEL_ORDER = [
    "PERSON",
    "DRUG",
    "DRUG_WEIGHT",
    "CRIME_TIME",
    "CRIME_LOC",
    "CHARGE",
    "SENTENCE",
    "LEGAL_ARTICLE",
]


def load_jsonl(path: Path):
    data = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Lỗi JSON ở dòng {line_no}: {e}") from e
    return data


def normalize_split_name(value):
    value = str(value).strip().lower()
    if value in {"train", "training"}:
        return "Training"
    if value in {"val", "valid", "validation", "dev"}:
        return "Validation"
    if value in {"test", "testing"}:
        return "Testing"
    return value.title()


def get_existing_split(item):
    split = item.get("split")
    if split:
        return normalize_split_name(split)

    meta = item.get("meta") or {}
    split = meta.get("split")
    if split:
        return normalize_split_name(split)

    return None


def get_source(item, index):
    meta = item.get("meta") or {}
    return meta.get("source") or item.get("source") or f"__row_{index}"


def assign_split_by_source(data, train_ratio=0.8, val_ratio=0.1, seed=42):
    """
    Chia theo bản án/source để tránh data leakage:
    các đoạn của cùng 1 bản án không bị rơi vào nhiều tập.
    """
    sources = sorted({get_source(item, i) for i, item in enumerate(data)})
    rng = random.Random(seed)
    rng.shuffle(sources)

    n = len(sources)
    n_train = int(round(n * train_ratio))
    n_val = int(round(n * val_ratio))

    train_sources = set(sources[:n_train])
    val_sources = set(sources[n_train:n_train + n_val])

    split_map = {}
    for i, item in enumerate(data):
        source = get_source(item, i)
        if source in train_sources:
            split_map[i] = "Training"
        elif source in val_sources:
            split_map[i] = "Validation"
        else:
            split_map[i] = "Testing"

    return split_map


def build_split_map(data, seed=42, train_ratio=0.8, val_ratio=0.1):
    existing = [get_existing_split(item) for item in data]

    if all(split is not None for split in existing):
        return {i: existing[i] for i in range(len(data))}, True

    return assign_split_by_source(
        data,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    ), False


def iter_labels(item):
    labels = item.get("labels")
    if labels is None:
        labels = item.get("label")
    if labels is None:
        labels = item.get("entities", [])

    for ent in labels:
        if isinstance(ent, list) and len(ent) >= 3:
            yield ent[2]
        elif isinstance(ent, dict):
            label = ent.get("label") or ent.get("entity")
            if label:
                yield label


def count_entities(data, split_map):
    split_counters = {
        "Training": Counter(),
        "Validation": Counter(),
        "Testing": Counter(),
        "All": Counter(),
    }

    row_counts = {
        "Training": 0,
        "Validation": 0,
        "Testing": 0,
        "All": len(data),
    }

    source_sets = {
        "Training": set(),
        "Validation": set(),
        "Testing": set(),
        "All": set(),
    }

    for i, item in enumerate(data):
        split = split_map[i]
        source = get_source(item, i)

        row_counts[split] += 1
        source_sets[split].add(source)
        source_sets["All"].add(source)

        for label in iter_labels(item):
            split_counters[split][label] += 1
            split_counters["All"][label] += 1

    return split_counters, row_counts, source_sets


def make_stats_rows(data, split_map, label_order=None):
    if label_order is None:
        label_order = DEFAULT_LABEL_ORDER

    split_counters, row_counts, source_sets = count_entities(data, split_map)

    observed_labels = sorted(split_counters["All"].keys())
    labels = [x for x in label_order if x in observed_labels]
    labels += [x for x in observed_labels if x not in labels]

    rows = []
    for label in labels:
        rows.append({
            "Entity type": label,
            "Training": split_counters["Training"][label],
            "Validation": split_counters["Validation"][label],
            "Testing": split_counters["Testing"][label],
            "All": split_counters["All"][label],
        })

    rows.append({
        "Entity type": "#Entities in total",
        "Training": sum(split_counters["Training"].values()),
        "Validation": sum(split_counters["Validation"].values()),
        "Testing": sum(split_counters["Testing"].values()),
        "All": sum(split_counters["All"].values()),
    })

    rows.append({
        "Entity type": "#Rows/snippets in total",
        "Training": row_counts["Training"],
        "Validation": row_counts["Validation"],
        "Testing": row_counts["Testing"],
        "All": row_counts["All"],
    })

    rows.append({
        "Entity type": "#Source judgments in total",
        "Training": len(source_sets["Training"]),
        "Validation": len(source_sets["Validation"]),
        "Testing": len(source_sets["Testing"]),
        "All": len(source_sets["All"]),
    })

    return rows


def print_table(rows):
    headers = ["Entity type", "Training", "Validation", "Testing", "All"]
    widths = {
        h: max(len(h), max(len(f"{row[h]:,}") if h != "Entity type" else len(str(row[h])) for row in rows))
        for h in headers
    }

    line = "  ".join(h.ljust(widths[h]) if h == "Entity type" else h.rjust(widths[h]) for h in headers)
    sep = "-" * len(line)

    print(line)
    print(sep)

    for row in rows:
        print(
            "  ".join(
                str(row[h]).ljust(widths[h]) if h == "Entity type" else f"{row[h]:,}".rjust(widths[h])
                for h in headers
            )
        )


def write_csv(rows, out_path: Path):
    headers = ["Entity type", "Training", "Validation", "Testing", "All"]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows, out_path: Path):
    headers = ["Entity type", "Training", "Validation", "Testing", "All"]

    def fmt(value):
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] + ["---:"] * 4) + " |")

    for row in rows:
        lines.append("| " + " | ".join(fmt(row[h]) for h in headers) + " |")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_split_files(data, split_map, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "Training": (out_dir / "train.jsonl").open("w", encoding="utf-8"),
        "Validation": (out_dir / "validation.jsonl").open("w", encoding="utf-8"),
        "Testing": (out_dir / "test.jsonl").open("w", encoding="utf-8"),
    }

    try:
        for i, item in enumerate(data):
            split = split_map[i]
            item = dict(item)
            meta = dict(item.get("meta") or {})
            meta["split"] = split.lower()
            item["meta"] = meta
            files[split].write(json.dumps(item, ensure_ascii=False) + "\n")
    finally:
        for f in files.values():
            f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Đường dẫn file drug.jsonl")
    parser.add_argument("--out_dir", default="split_stats_output", help="Thư mục output")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train_ratio", type=float, default=0.8)
    parser.add_argument("--val_ratio", type=float, default=0.1)
    parser.add_argument("--write_split_files", action="store_true", help="Xuất train/validation/test jsonl")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_jsonl(input_path)
    split_map, used_existing_split = build_split_map(
        data,
        seed=args.seed,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )

    rows = make_stats_rows(data, split_map)

    print()
    print(f"Input: {input_path}")
    print(f"Số dòng/snippet: {len(data):,}")
    print("Split:", "dùng split có sẵn trong file" if used_existing_split else "file chưa có split, đã chia theo meta.source")
    print()

    print_table(rows)

    csv_path = out_dir / "split_statistics.csv"
    md_path = out_dir / "split_statistics.md"

    write_csv(rows, csv_path)
    write_markdown(rows, md_path)

    if args.write_split_files:
        write_split_files(data, split_map, out_dir)

    print()
    print(f"Đã lưu CSV: {csv_path}")
    print(f"Đã lưu Markdown: {md_path}")
    if args.write_split_files:
        print(f"Đã lưu split files: {out_dir / 'train.jsonl'}, {out_dir / 'validation.jsonl'}, {out_dir / 'test.jsonl'}")


if __name__ == "__main__":
    main()
