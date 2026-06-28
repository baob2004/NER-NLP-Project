# -*- coding: utf-8 -*-
"""
make_shared_split.py
====================
Tạo 1 bộ train/dev/test cố định theo document/source để dùng chung cho
PhoBERT, XLM-RoBERTa và spaCy.

Chạy:
    python make_shared_split.py --data ../data/annotated/drug.jsonl --output ../data/splits/shared --seed 42 --train-ratio 0.85 --dev-ratio 0.10
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from dataset_loader import load_all_data, split_by_doc


def get_source(record, index):
    meta = record.get("meta") or {}
    return (
        meta.get("source")
        or meta.get("file")
        or meta.get("filename")
        or record.get("source")
        or record.get("filename")
        or f"__row_{index}"
    )


def get_entities(record):
    raw = record.get("labels") or record.get("label") or record.get("entities") or []
    entities = []
    for ent in raw:
        if isinstance(ent, list) and len(ent) >= 3:
            start, end, label = ent[0], ent[1], ent[2]
        elif isinstance(ent, dict):
            start = ent.get("start")
            end = ent.get("end")
            label = ent.get("label") or ent.get("entity")
        else:
            continue
        if label:
            entities.append(str(label))
    return entities


def save_jsonl(records, path: Path, split_name: str):
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            obj = dict(rec)
            meta = dict(obj.get("meta") or {})
            meta["split"] = split_name
            obj["meta"] = meta
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def count_stats(records):
    label_counter = Counter()
    sources = set()
    for i, rec in enumerate(records):
        sources.add(get_source(rec, i))
        label_counter.update(get_entities(rec))
    return {
        "records": len(records),
        "documents": len(sources),
        "entities": sum(label_counter.values()),
        "labels": dict(label_counter),
    }


def main():
    parser = argparse.ArgumentParser(description="Tạo shared split train/dev/test cho mọi model")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("../data/splits/shared"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.85)
    parser.add_argument("--dev-ratio", type=float, default=0.10)
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Không tìm thấy data: {args.data}")

    args.output.mkdir(parents=True, exist_ok=True)

    records = load_all_data(args.data)
    train_recs, dev_recs, test_recs = split_by_doc(
        records,
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )

    train_path = args.output / "train.jsonl"
    dev_path = args.output / "dev.jsonl"
    test_path = args.output / "test.jsonl"

    save_jsonl(train_recs, train_path, "train")
    save_jsonl(dev_recs, dev_path, "dev")
    save_jsonl(test_recs, test_path, "test")

    report = {
        "data": str(args.data),
        "seed": args.seed,
        "train_ratio": args.train_ratio,
        "dev_ratio": args.dev_ratio,
        "test_ratio": round(1 - args.train_ratio - args.dev_ratio, 10),
        "files": {
            "train": str(train_path),
            "dev": str(dev_path),
            "test": str(test_path),
        },
        "stats": {
            "train": count_stats(train_recs),
            "dev": count_stats(dev_recs),
            "test": count_stats(test_recs),
            "all": count_stats(records),
        },
    }

    report_path = args.output / "split_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Đã tạo shared split:")
    print(f"- Train: {train_path} | records={len(train_recs)}")
    print(f"- Dev  : {dev_path} | records={len(dev_recs)}")
    print(f"- Test : {test_path} | records={len(test_recs)}")
    print(f"- Report: {report_path}")


if __name__ == "__main__":
    main()
