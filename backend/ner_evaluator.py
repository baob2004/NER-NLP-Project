from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score


def decode_predictions(logits, label_ids, id2label: Dict[int, str]):
    preds = np.argmax(logits, axis=-1)

    true_seqs: List[List[str]] = []
    pred_seqs: List[List[str]] = []

    for pred_row, label_row in zip(preds, label_ids):
        true_seq: List[str] = []
        pred_seq: List[str] = []

        for p, l in zip(pred_row, label_row):
            if int(l) == -100:
                continue
            true_seq.append(id2label.get(int(l), "O"))
            pred_seq.append(id2label.get(int(p), "O"))

        if true_seq:
            true_seqs.append(true_seq)
            pred_seqs.append(pred_seq)

    return true_seqs, pred_seqs


def evaluate_model(model, dataloader, device, id2label: Dict[int, str]) -> dict:
    model.eval()
    all_true: List[List[str]] = []
    all_pred: List[List[str]] = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits.detach().cpu().numpy()
            label_ids = labels.detach().cpu().numpy()

            true_seqs, pred_seqs = decode_predictions(logits, label_ids, id2label)
            all_true.extend(true_seqs)
            all_pred.extend(pred_seqs)

    report = classification_report(
        all_true,
        all_pred,
        output_dict=True,
        zero_division=0,
    )

    results = {}
    for key, val in report.items():
        if key in ("micro avg", "macro avg", "weighted avg", "accuracy"):
            continue
        results[key] = {
            "precision": round(val["precision"], 4),
            "recall": round(val["recall"], 4),
            "f1": round(val["f1-score"], 4),
            "support": int(val["support"]),
        }

    results["overall"] = {
        "precision": round(precision_score(all_true, all_pred, zero_division=0), 4),
        "recall": round(recall_score(all_true, all_pred, zero_division=0), 4),
        "f1": round(f1_score(all_true, all_pred, zero_division=0), 4),
        "support": sum(v["support"] for k, v in results.items() if k != "overall"),
    }

    return results


def print_results(results: dict) -> None:
    print("─" * 62)
    print(f"{'Nhãn':18s} {'Precision':>10s} {'Recall':>10s} {'F1':>10s} {'Support':>8s}")
    print("─" * 62)
    for label, score in results.items():
        if label == "overall":
            continue
        print(
            f"{label:18s} "
            f"{score['precision']:10.4f} "
            f"{score['recall']:10.4f} "
            f"{score['f1']:10.4f} "
            f"{score['support']:8d}"
        )
    print("─" * 62)
    ov = results["overall"]
    print(
        f"{'OVERALL':18s} "
        f"{ov['precision']:10.4f} "
        f"{ov['recall']:10.4f} "
        f"{ov['f1']:10.4f} "
        f"{ov['support']:8d}"
    )
    print("─" * 62)
