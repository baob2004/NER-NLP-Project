# -*- coding: utf-8 -*-
"""
train.py
========
Train PhoBERT NER cho bản án ma túy với dữ liệu ít/lệch nhãn.

Ưu điểm:
    - Không dùng HuggingFace Trainer -> tránh lỗi version transformers.
    - Không dùng offset_mapping -> tránh lỗi PhoBERT không trả offset.
    - Tokenize thủ công từng word để tương thích slow tokenizer PhoBERT.
    - Weighted CrossEntropyLoss theo 8 nhãn hiện tại:
        PERSON, DRUG, CRIME_TIME, CRIME_LOC, DRUG_WEIGHT,
        CHARGE, SENTENCE, LEGAL_ARTICLE
    - Xuất BIO debug để kiểm tra nhãn trước khi train.

Cài:
    pip install -q torch transformers seqeval scikit-learn numpy tqdm

Chạy:
    python train.py --data ../data/annotated/drug.jsonl --output ../models/phobert-ner-weighted --epochs 40 --batch 4 --lr 3e-5

Chỉ xuất BIO debug:
    python train.py --data ../data/annotated/drug.jsonl --output ../models/phobert-ner-weighted --bio-only
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Dict

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tqdm.auto import tqdm
from transformers import AutoModelForTokenClassification, AutoTokenizer, get_linear_schedule_with_warmup

from dataset_loader import (
    ENTITY_LABELS,
    ID2LABEL,
    LABEL2ID,
    LABELS,
    NERDataset,
    count_word_labels,
    export_bio_debug,
    load_all_data,
    print_label_distribution,
    split_by_doc,
)
from evaluate import evaluate_model, print_results


DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "annotated" / "drug.jsonl"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "models" / "phobert-ner-weighted"
DEFAULT_MODEL = "vinai/phobert-base-v2"

# Prior theo số span gần nhất của bộ dữ liệu 8 nhãn.
# Chỉ dùng để khởi tạo class weights; có thể bỏ qua bằng --no-prior-weights
# để tính trực tiếp từ file train.
PRIOR_ENTITY_COUNTS = {
    "DRUG": 519,
    "DRUG_WEIGHT": 152,
    "CRIME_TIME": 256,
    "CRIME_LOC": 451,
    "PERSON": 207,
    "CHARGE": 116,
    "LEGAL_ARTICLE": 322,
    "SENTENCE": 127,
}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_class_weights(records, device, use_prior: bool = True) -> torch.Tensor:
    """
    Tạo class weights cho CrossEntropyLoss.

    Vì O cực nhiều, entity ít, nếu không weight model dễ predict toàn O.
    Weight được cap để không quá lớn.
    """
    weights = torch.ones(len(LABELS), dtype=torch.float, device=device)

    if use_prior:
        # Trọng số nghịch căn theo số entity bạn thống kê.
        max_count = max(PRIOR_ENTITY_COUNTS.values())
        for ent, cnt in PRIOR_ENTITY_COUNTS.items():
            w = math.sqrt(max_count / max(cnt, 1))
            w = min(max(w, 1.0), 3.0)
            weights[LABEL2ID[f"B-{ent}"]] = w
            weights[LABEL2ID[f"I-{ent}"]] = w
        weights[LABEL2ID["O"]] = 0.25
        return weights

    counter = count_word_labels(records)
    # Tính từ BIO word labels thật.
    entity_counts = {
        lab: counter.get(f"B-{lab}", 0) + counter.get(f"I-{lab}", 0)
        for lab in ENTITY_LABELS
    }
    max_count = max(entity_counts.values()) if entity_counts else 1
    for ent, cnt in entity_counts.items():
        if cnt <= 0:
            w = 2.5
        else:
            w = math.sqrt(max_count / cnt)
        w = min(max(w, 1.0), 3.0)
        weights[LABEL2ID[f"B-{ent}"]] = w
        weights[LABEL2ID[f"I-{ent}"]] = w

    weights[LABEL2ID["O"]] = 0.25
    return weights


def weighted_loss(logits, labels, class_weights):
    """
    logits: [B, T, C]
    labels: [B, T], có -100
    """
    loss_fn = nn.CrossEntropyLoss(weight=class_weights, ignore_index=-100)
    return loss_fn(logits.view(-1, logits.size(-1)), labels.view(-1))


def save_label_config(out_dir: Path) -> None:
    with (out_dir / "label_config.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "labels": LABELS,
                "label2id": LABEL2ID,
                "id2label": {str(k): v for k, v in ID2LABEL.items()},
                "entity_counts_used_for_weight": PRIOR_ENTITY_COUNTS,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )



def save_jsonl(records, path: Path, split_name: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            obj = dict(rec)
            meta = dict(obj.get("meta") or {})
            meta["split"] = split_name
            obj["meta"] = meta
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def make_or_load_split(records, args, output_dir: Path):
    """
    Nếu truyền --train-file/--dev-file/--test-file thì dùng đúng split có sẵn.
    Nếu không, tự split và lưu ra output_dir/splits để các model khác dùng lại.
    """
    if args.train_file and args.dev_file and args.test_file:
        print("Dùng shared split có sẵn:")
        print(f"  Train: {args.train_file}")
        print(f"  Dev  : {args.dev_file}")
        print(f"  Test : {args.test_file}")
        return (
            load_all_data(args.train_file),
            load_all_data(args.dev_file),
            load_all_data(args.test_file),
        )

    print("Chưa truyền split file -> tự split theo document/source và lưu lại.")
    train_recs, dev_recs, test_recs = split_by_doc(
        records,
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )

    split_dir = output_dir / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    save_jsonl(train_recs, split_dir / "train.jsonl", "train")
    save_jsonl(dev_recs, split_dir / "dev.jsonl", "dev")
    save_jsonl(test_recs, split_dir / "test.jsonl", "test")

    with (split_dir / "split_report.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "seed": args.seed,
                "train_ratio": args.train_ratio,
                "dev_ratio": args.dev_ratio,
                "test_ratio": round(1 - args.train_ratio - args.dev_ratio, 10),
                "train_records": len(train_recs),
                "dev_records": len(dev_recs),
                "test_records": len(test_recs),
                "train_file": str(split_dir / "train.jsonl"),
                "dev_file": str(split_dir / "dev.jsonl"),
                "test_file": str(split_dir / "test.jsonl"),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Đã lưu split chung -> {split_dir}")
    return train_recs, dev_recs, test_recs


def train(args):
    set_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/6] Load data: {args.data}")
    records = load_all_data(args.data)
    print(f"Records: {len(records)}")
    if not records:
        raise SystemExit("Không có record nào.")

    export_bio_debug(records, output_dir / "drug_ner_debug.conll")
    print(f"BIO debug -> {output_dir / 'drug_ner_debug.conll'}")
    print_label_distribution(records)

    if args.bio_only:
        print("\nĐã xuất BIO debug. Dừng vì --bio-only.")
        return

    print("\n[2/6] Split data")
    train_recs, dev_recs, test_recs = make_or_load_split(records, args, output_dir)
    print(f"Train records: {len(train_recs)} | Dev records: {len(dev_recs)} | Test records: {len(test_recs)}")

    print(f"\n[3/6] Load tokenizer/model: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )
    model.to(device)

    train_ds = NERDataset(train_recs, tokenizer, args.max_len)
    dev_ds = NERDataset(dev_recs, tokenizer, args.max_len)
    test_ds = NERDataset(test_recs, tokenizer, args.max_len)

    batch_size = min(args.batch, max(1, len(train_ds)))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    dev_loader = DataLoader(dev_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    class_weights = build_class_weights(train_recs, device, use_prior=not args.no_prior_weights)
    print("\nClass weights:")
    for lab, idx in LABEL2ID.items():
        print(f"  {lab:18s}: {float(class_weights[idx]):.4f}")

    print("\n[4/6] Optimizer/Scheduler")
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = max(1, len(train_loader) * args.epochs)
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    best_f1 = -1.0
    no_improve = 0
    best_dir = output_dir / "best_model"

    print("\n[5/6] Training")
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}", leave=False)
        for batch in pbar:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = weighted_loss(outputs.logits, labels, class_weights)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            scheduler.step()

            total_loss += float(loss.item())
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        avg_loss = total_loss / max(1, len(train_loader))
        dev_results = evaluate_model(model, dev_loader, device, ID2LABEL)
        dev_f1 = dev_results["overall"]["f1"]

        print(f"\nEpoch {epoch:02d} | loss={avg_loss:.4f} | dev_f1={dev_f1:.4f} | best={best_f1:.4f}")
        print_results(dev_results)

        if dev_f1 > best_f1:
            best_f1 = dev_f1
            no_improve = 0
            best_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(best_dir)
            tokenizer.save_pretrained(best_dir)
            save_label_config(best_dir)
            print(f"Saved best model -> {best_dir}")
        else:
            no_improve += 1
            if no_improve >= args.early_stop:
                print(f"Early stopping sau {args.early_stop} epochs không cải thiện.")
                break

    print("\n[6/6] Test best model")
    best_model = AutoModelForTokenClassification.from_pretrained(best_dir).to(device)
    test_results = evaluate_model(best_model, test_loader, device, ID2LABEL)
    print_results(test_results)

    with (output_dir / "test_results.json").open("w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    print(f"\nBest model: {best_dir}")
    print(f"Test results: {output_dir / 'test_results.json'}")


def main():
    parser = argparse.ArgumentParser(description="Train PhoBERT weighted NER 8 nhãn cho bản án ma túy")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.85)
    parser.add_argument("--dev-ratio", type=float, default=0.10)
    parser.add_argument("--early-stop", type=int, default=8)
    parser.add_argument("--train-file", type=Path, default=None, help="File train.jsonl shared split")
    parser.add_argument("--dev-file", type=Path, default=None, help="File dev.jsonl shared split")
    parser.add_argument("--test-file", type=Path, default=None, help="File test.jsonl shared split")
    parser.add_argument("--bio-only", action="store_true")
    parser.add_argument("--no-prior-weights", action="store_true", help="Không dùng prior counts bạn cung cấp, tính weight từ data.")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Không tìm thấy file data: {args.data}")

    for split_path in [args.train_file, args.dev_file, args.test_file]:
        if split_path is not None and not split_path.exists():
            raise SystemExit(f"Không tìm thấy split file: {split_path}")

    train(args)


if __name__ == "__main__":
    main()
