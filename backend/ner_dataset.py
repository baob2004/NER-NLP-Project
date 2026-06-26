from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import torch
from torch.utils.data import Dataset


ENTITY_LABELS = [
    "PERSON",
    "DRUG",
    "CRIME_TIME",
    "CRIME_LOC",
    "DRUG_WEIGHT",
    "CHARGE",
    "SENTENCE",
    "LEGAL_ARTICLE",
]

LABEL_ALIASES = {
    "DEFENDANT": "PERSON",
}

LABELS = ["O"]
for ent in ENTITY_LABELS:
    LABELS.append(f"B-{ent}")
    LABELS.append(f"I-{ent}")

LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}


def read_jsonl(path: str | Path) -> List[dict]:
    path = Path(path)
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                print(f"[WARN] Bỏ dòng {line_no} trong {path.name}: JSON lỗi: {e}")
                continue

            if "text" not in obj:
                print(f"[WARN] Bỏ dòng {line_no} trong {path.name}: thiếu text")
                continue

            labels = obj.get("labels", obj.get("label", []))
            if labels is None:
                labels = []
            obj["labels"] = labels
            records.append(obj)
    return records


def load_all_data(annotated_path: str | Path) -> List[dict]:
    p = Path(annotated_path)
    if p.is_file():
        return read_jsonl(p)

    files = sorted(p.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"Không tìm thấy file .jsonl trong: {p}")

    all_records: List[dict] = []
    for fp in files:
        recs = read_jsonl(fp)
        for r in recs:
            r.setdefault("meta", {})
            r["meta"].setdefault("source_file", fp.name)
        all_records.extend(recs)
    return all_records


_WORD_RE = re.compile(r"\S+", flags=re.UNICODE)


def split_words_with_offsets(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    words: List[str] = []
    offsets: List[Tuple[int, int]] = []
    for m in _WORD_RE.finditer(text):
        words.append(m.group(0))
        offsets.append((m.start(), m.end()))
    return words, offsets


def _normalize_spans(raw_labels: Iterable, text_len: int) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    for item in raw_labels:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        s, e, label = item
        try:
            s = int(s)
            e = int(e)
        except Exception:
            continue
        label = LABEL_ALIASES.get(str(label), str(label))
        if label not in ENTITY_LABELS:
            continue
        if not (0 <= s < e <= text_len):
            continue
        spans.append((s, e, label))

    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    return spans


def _span_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def char_spans_to_word_bio(text: str, raw_labels: Iterable) -> Tuple[List[str], List[str]]:
    words, word_offsets = split_words_with_offsets(text)
    labels = ["O"] * len(words)
    spans = _normalize_spans(raw_labels, len(text))

    for s, e, ent in spans:
        inside_indices = [
            i for i, (ws, we) in enumerate(word_offsets)
            if _span_overlap(ws, we, s, e)
        ]
        if not inside_indices:
            continue

        first = True
        for i in inside_indices:
            labels[i] = f"{'B' if first else 'I'}-{ent}"
            first = False

    return words, labels


def records_to_word_items(records: List[dict]) -> List[dict]:
    items: List[dict] = []
    for idx, r in enumerate(records):
        text = r.get("text", "")
        words, labels = char_spans_to_word_bio(text, r.get("labels", []))
        if not words:
            continue
        items.append({
            "id": r.get("id", idx),
            "text": text,
            "tokens": words,
            "labels": labels,
            "meta": r.get("meta", {}),
        })
    return items


def split_by_doc(
    records: List[dict],
    seed: int = 42,
    train_ratio: float = 0.85,
    dev_ratio: float = 0.10,
) -> Tuple[List[dict], List[dict], List[dict]]:
    rng = random.Random(seed)

    groups: Dict[str, List[dict]] = {}
    for i, r in enumerate(records):
        meta = r.get("meta", {}) or {}
        key = (
            meta.get("source")
            or meta.get("source_file")
            or meta.get("file")
            or str(r.get("id", i))
        )
        groups.setdefault(str(key), []).append(r)

    keys = list(groups.keys())
    rng.shuffle(keys)

    n = len(keys)
    n_train = max(1, int(n * train_ratio))
    n_dev = max(1, int(n * dev_ratio)) if n >= 10 else max(1, n - n_train)

    train_keys = set(keys[:n_train])
    dev_keys = set(keys[n_train:n_train + n_dev])
    test_keys = set(keys[n_train + n_dev:])

    if not test_keys and len(train_keys) > 1:
        moved = next(iter(train_keys))
        train_keys.remove(moved)
        test_keys.add(moved)

    train, dev, test = [], [], []
    for k, rs in groups.items():
        if k in train_keys:
            train.extend(rs)
        elif k in dev_keys:
            dev.extend(rs)
        else:
            test.extend(rs)

    return train, dev, test


def _manual_encode_words(tokenizer, words: List[str], word_labels: List[str], max_length: int):
    input_ids: List[int] = []
    label_ids: List[int] = []

    if tokenizer.cls_token_id is not None:
        input_ids.append(tokenizer.cls_token_id)
        label_ids.append(-100)
    elif tokenizer.bos_token_id is not None:
        input_ids.append(tokenizer.bos_token_id)
        label_ids.append(-100)

    sep_id = tokenizer.sep_token_id if tokenizer.sep_token_id is not None else tokenizer.eos_token_id
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 1

    max_body_len = max_length - 1

    for word, lab in zip(words, word_labels):
        sub_ids = tokenizer.encode(word, add_special_tokens=False)
        if not sub_ids:
            sub_ids = [tokenizer.unk_token_id] if tokenizer.unk_token_id is not None else []

        if not sub_ids:
            continue

        if len(input_ids) + len(sub_ids) > max_body_len:
            break

        for j, sid in enumerate(sub_ids):
            input_ids.append(sid)
            label_ids.append(LABEL2ID.get(lab, LABEL2ID["O"]) if j == 0 else -100)

    if sep_id is not None and len(input_ids) < max_length:
        input_ids.append(sep_id)
        label_ids.append(-100)

    attention_mask = [1] * len(input_ids)

    if len(input_ids) < max_length:
        pad_len = max_length - len(input_ids)
        input_ids += [pad_id] * pad_len
        attention_mask += [0] * pad_len
        label_ids += [-100] * pad_len

    return {
        "input_ids": torch.tensor(input_ids[:max_length], dtype=torch.long),
        "attention_mask": torch.tensor(attention_mask[:max_length], dtype=torch.long),
        "labels": torch.tensor(label_ids[:max_length], dtype=torch.long),
    }


class NERDataset(Dataset):
    def __init__(self, records: List[dict], tokenizer, max_length: int = 256):
        self.items = records_to_word_items(records)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> dict:
        item = self.items[idx]
        return _manual_encode_words(
            self.tokenizer,
            item["tokens"],
            item["labels"],
            self.max_length,
        )


def count_word_labels(records: List[dict]) -> Counter:
    counter = Counter()
    for item in records_to_word_items(records):
        counter.update(item["labels"])
    return counter


def export_bio_debug(records: List[dict], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for item in records_to_word_items(records):
            for tok, lab in zip(item["tokens"], item["labels"]):
                f.write(f"{tok}\t{lab}\n")
            f.write("\n")


def print_label_distribution(records: List[dict]) -> None:
    counter = count_word_labels(records)
    print("\nLabel distribution word-level:")
    for lab in LABELS:
        print(f"  {lab:18s}: {counter.get(lab, 0)}")
