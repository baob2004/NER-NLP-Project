# train_spacy_ner.py
# Huấn luyện mô hình spaCy NER để so sánh với PhoBERT
# Input: Doccano JSONL dạng {"text": "...", "labels": [[start, end, "LABEL"], ...]}
# Output:
#   - model-best/
#   - model-last/
#   - test_results.json
#   - test_results_table.csv
#   - spacy_split_stats.csv

import argparse
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import spacy
from spacy.training import Example
from spacy.util import compounding, minibatch


LABELS = [
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
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Lỗi JSON ở dòng {line_no}: {e}") from e

            if "text" not in obj:
                raise ValueError(f"Dòng {line_no} không có field 'text'")

            records.append(obj)

    return records


def get_entities(record):
    """
    Hỗ trợ:
    - labels: [[start, end, label], ...]
    - label: [[start, end, label], ...]
    - entities: [{"start":..., "end":..., "label":...}, ...]
    """
    if "labels" in record:
        raw = record["labels"]
    elif "label" in record:
        raw = record["label"]
    elif "entities" in record:
        raw = record["entities"]
    else:
        raw = []

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

        if start is None or end is None or not label:
            continue

        try:
            start = int(start)
            end = int(end)
        except Exception:
            continue

        if start < 0 or end <= start or end > len(record["text"]):
            continue

        if label not in LABELS:
            continue

        entities.append((start, end, label))

    # sort + remove overlap for spaCy
    entities = sorted(entities, key=lambda x: (x[0], x[1]))
    clean = []
    last_end = -1

    for start, end, label in entities:
        if start < last_end:
            # spaCy không nhận span overlap
            continue
        clean.append((start, end, label))
        last_end = end

    return clean


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


def split_by_doc(records, seed=42, train_ratio=0.8, dev_ratio=0.1):
    """
    Chia theo document/bản án, không chia theo từng dòng.
    Tránh leakage: các snippet của cùng một bản án không rơi vào nhiều tập.
    """
    sources = sorted({get_source(rec, i) for i, rec in enumerate(records)})

    rng = random.Random(seed)
    rng.shuffle(sources)

    n = len(sources)
    n_train = int(round(n * train_ratio))
    n_dev = int(round(n * dev_ratio))

    train_sources = set(sources[:n_train])
    dev_sources = set(sources[n_train:n_train + n_dev])

    train_recs, dev_recs, test_recs = [], [], []

    for i, rec in enumerate(records):
        source = get_source(rec, i)
        if source in train_sources:
            train_recs.append(rec)
        elif source in dev_sources:
            dev_recs.append(rec)
        else:
            test_recs.append(rec)

    return train_recs, dev_recs, test_recs


def records_to_examples(nlp, records, name="dataset"):
    examples = []
    skipped = 0
    misaligned = 0

    for rec in records:
        text = rec["text"]
        entities = get_entities(rec)

        doc = nlp.make_doc(text)
        valid_ents = []

        for start, end, label in entities:
            span = doc.char_span(start, end, label=label, alignment_mode="contract")

            if span is None:
                misaligned += 1
                span = doc.char_span(start, end, label=label, alignment_mode="expand")

            if span is not None:
                valid_ents.append((span.start_char, span.end_char, label))

        try:
            example = Example.from_dict(doc, {"entities": valid_ents})
            examples.append(example)
        except Exception:
            skipped += 1

    print(f"{name}: examples={len(examples)} | skipped={skipped} | misaligned_fixed={misaligned}")
    return examples


def count_entities(records):
    counter = Counter()

    for rec in records:
        for _, _, label in get_entities(rec):
            counter[label] += 1

    return counter


def save_split_stats(train_recs, dev_recs, test_recs, out_dir: Path):
    split_map = {
        "Training": train_recs,
        "Validation": dev_recs,
        "Testing": test_recs,
    }

    rows = []
    for label in LABELS:
        row = {"Entity type": label}
        total = 0

        for split_name, recs in split_map.items():
            c = count_entities(recs)[label]
            row[split_name] = c
            total += c

        row["All"] = total
        rows.append(row)

    rows.append({
        "Entity type": "#Entities in total",
        "Training": sum(count_entities(train_recs).values()),
        "Validation": sum(count_entities(dev_recs).values()),
        "Testing": sum(count_entities(test_recs).values()),
        "All": (
            sum(count_entities(train_recs).values())
            + sum(count_entities(dev_recs).values())
            + sum(count_entities(test_recs).values())
        ),
    })

    rows.append({
        "Entity type": "#Rows/snippets in total",
        "Training": len(train_recs),
        "Validation": len(dev_recs),
        "Testing": len(test_recs),
        "All": len(train_recs) + len(dev_recs) + len(test_recs),
    })

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "spacy_split_stats.csv", index=False, encoding="utf-8-sig")

    print("\nSplit statistics:")
    print(df.to_string(index=False))

    return df


def create_spacy_model():
    """
    spaCy không phải transformer ở đây.
    Dùng blank multilingual 'xx' cho an toàn với tiếng Việt.
    """
    try:
        nlp = spacy.blank("vi")
        print("Using spaCy blank language: vi")
    except Exception:
        nlp = spacy.blank("xx")
        print("spaCy blank('vi') không khả dụng, fallback sang blank('xx')")

    if "ner" not in nlp.pipe_names:
        ner = nlp.add_pipe("ner")
    else:
        ner = nlp.get_pipe("ner")

    for label in LABELS:
        ner.add_label(label)

    return nlp


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f


def evaluate_exact_match(nlp, records):
    """
    Entity-level exact match:
    đúng khi start, end, label đều giống gold.
    """
    gold_by_label = Counter()
    pred_by_label = Counter()
    tp_by_label = Counter()

    for rec in records:
        text = rec["text"]
        gold = set(get_entities(rec))

        doc = nlp(text)
        pred = set((ent.start_char, ent.end_char, ent.label_) for ent in doc.ents)

        for _, _, label in gold:
            gold_by_label[label] += 1

        for _, _, label in pred:
            if label in LABELS:
                pred_by_label[label] += 1

        for item in gold & pred:
            _, _, label = item
            tp_by_label[label] += 1

    results = {}

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for label in LABELS:
        tp = tp_by_label[label]
        fp = pred_by_label[label] - tp
        fn = gold_by_label[label] - tp

        precision, recall, f1 = prf(tp, fp, fn)

        results[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": gold_by_label[label],
            "predicted": pred_by_label[label],
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

        total_tp += tp
        total_fp += fp
        total_fn += fn

    p, r, f = prf(total_tp, total_fp, total_fn)

    results["overall"] = {
        "precision": p,
        "recall": r,
        "f1": f,
        "support": sum(gold_by_label.values()),
        "predicted": sum(pred_by_label.values()),
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
    }

    return results


def results_to_dataframe(results):
    rows = []

    for label in LABELS:
        score = results[label]
        rows.append({
            "Nhãn": label,
            "Precision": score["precision"],
            "Recall": score["recall"],
            "F1": score["f1"],
            "Support": score["support"],
            "Predicted": score["predicted"],
        })

    overall = results["overall"]
    rows.append({
        "Nhãn": "OVERALL",
        "Precision": overall["precision"],
        "Recall": overall["recall"],
        "F1": overall["f1"],
        "Support": overall["support"],
        "Predicted": overall["predicted"],
    })

    return pd.DataFrame(rows)


def print_results(results):
    df = results_to_dataframe(results)

    print("\nEvaluation:")
    print("────────────────────────────────────────────────────────────────────────────")
    print(f"{'Nhãn':<18} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>8} {'Pred':>8}")
    print("────────────────────────────────────────────────────────────────────────────")

    for _, row in df.iterrows():
        print(
            f"{row['Nhãn']:<18} "
            f"{row['Precision']:>10.4f} "
            f"{row['Recall']:>10.4f} "
            f"{row['F1']:>10.4f} "
            f"{int(row['Support']):>8} "
            f"{int(row['Predicted']):>8}"
        )

    print("────────────────────────────────────────────────────────────────────────────")

    return df


def train_spacy(
    train_examples,
    dev_records,
    output_dir: Path,
    n_iter=40,
    dropout=0.25,
    batch_start=4.0,
    batch_stop=32.0,
    batch_compound=1.001,
    seed=42,
):
    random.seed(seed)
    spacy.util.fix_random_seed(seed)

    nlp = create_spacy_model()
    optimizer = nlp.initialize(lambda: train_examples)

    best_f1 = -1.0
    best_dir = output_dir / "model-best"
    last_dir = output_dir / "model-last"

    print("\nTraining spaCy NER")
    print(f"Epochs: {n_iter} | Dropout: {dropout}")

    for epoch in range(1, n_iter + 1):
        random.shuffle(train_examples)
        losses = {}

        batches = minibatch(
            train_examples,
            size=compounding(batch_start, batch_stop, batch_compound),
        )

        for batch in batches:
            nlp.update(
                batch,
                drop=dropout,
                sgd=optimizer,
                losses=losses,
            )

        dev_results = evaluate_exact_match(nlp, dev_records)
        dev_f1 = dev_results["overall"]["f1"]
        ner_loss = losses.get("ner", 0.0)

        print(f"Epoch {epoch:02d} | loss={ner_loss:.4f} | dev_f1={dev_f1:.4f} | best={best_f1:.4f}")

        if dev_f1 > best_f1:
            best_f1 = dev_f1

            if best_dir.exists():
                shutil.rmtree(best_dir)

            nlp.to_disk(best_dir)
            print(f"Saved best model -> {best_dir}")

    if last_dir.exists():
        shutil.rmtree(last_dir)
    nlp.to_disk(last_dir)

    return best_dir, last_dir


def save_jsonl(records, path: Path, split_name):
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            rec = dict(rec)
            meta = dict(rec.get("meta") or {})
            meta["split"] = split_name
            rec["meta"] = meta
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")



def make_or_load_split(records, args):
    """
    Nếu có --train-file/--dev-file/--test-file thì spaCy dùng đúng split chung.
    Nếu không có thì mới tự split theo tỷ lệ.
    """
    if args.train_file and args.dev_file and args.test_file:
        print("\nDùng shared split có sẵn:")
        print(f"Train: {args.train_file}")
        print(f"Dev  : {args.dev_file}")
        print(f"Test : {args.test_file}")
        return (
            load_jsonl(args.train_file),
            load_jsonl(args.dev_file),
            load_jsonl(args.test_file),
        )

    print("\nChưa truyền split file -> spaCy tự split theo document/source.")
    return split_by_doc(
        records,
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True, help="File annotated drug.jsonl")
    parser.add_argument("--out_dir", default="models/spacy-ner-drug", help="Thư mục output spaCy")
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--train-ratio", type=float, default=0.80)
    parser.add_argument("--dev-ratio", type=float, default=0.10)
    parser.add_argument("--train-file", type=Path, default=None, help="File train.jsonl shared split")
    parser.add_argument("--dev-file", type=Path, default=None, help="File dev.jsonl shared split")
    parser.add_argument("--test-file", type=Path, default=None, help="File test.jsonl shared split")

    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--dropout", type=float, default=0.25)

    parser.add_argument("--batch-start", type=float, default=4.0)
    parser.add_argument("--batch-stop", type=float, default=32.0)
    parser.add_argument("--batch-compound", type=float, default=1.001)

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Device/model: spaCy CPU/GPU tùy runtime")
    print(f"Input: {input_path}")
    print(f"Output: {output_dir}")

    records = load_jsonl(input_path)
    print(f"Records: {len(records)}")

    train_recs, dev_recs, test_recs = make_or_load_split(records, args)

    print("\nSplit data by document/source")
    print(f"Train records: {len(train_recs)}")
    print(f"Dev records  : {len(dev_recs)}")
    print(f"Test records : {len(test_recs)}")

    save_split_stats(train_recs, dev_recs, test_recs, output_dir)

    save_jsonl(train_recs, output_dir / "train.jsonl", "train")
    save_jsonl(dev_recs, output_dir / "dev.jsonl", "dev")
    save_jsonl(test_recs, output_dir / "test.jsonl", "test")

    # Model tạm để tạo examples
    nlp_for_examples = create_spacy_model()

    train_examples = records_to_examples(nlp_for_examples, train_recs, name="train")
    _ = records_to_examples(nlp_for_examples, dev_recs, name="dev")
    _ = records_to_examples(nlp_for_examples, test_recs, name="test")

    best_dir, last_dir = train_spacy(
        train_examples=train_examples,
        dev_records=dev_recs,
        output_dir=output_dir,
        n_iter=args.epochs,
        dropout=args.dropout,
        batch_start=args.batch_start,
        batch_stop=args.batch_stop,
        batch_compound=args.batch_compound,
        seed=args.seed,
    )

    print("\nTest best spaCy model")
    best_nlp = spacy.load(best_dir)
    test_results = evaluate_exact_match(best_nlp, test_recs)
    test_df = print_results(test_results)

    with (output_dir / "test_results.json").open("w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    test_df.to_csv(output_dir / "test_results_table.csv", index=False, encoding="utf-8-sig")

    print(f"\nSaved:")
    print(f"- Best model: {best_dir}")
    print(f"- Last model: {last_dir}")
    print(f"- Results JSON: {output_dir / 'test_results.json'}")
    print(f"- Results table: {output_dir / 'test_results_table.csv'}")


if __name__ == "__main__":
    main()
