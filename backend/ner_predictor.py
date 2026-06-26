from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Tuple

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer


def split_words_with_offsets(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    words, offsets = [], []
    for m in re.finditer(r"\S+", text, flags=re.UNICODE):
        words.append(m.group(0))
        offsets.append((m.start(), m.end()))
    return words, offsets


class NERPredictor:
    def __init__(self, model_dir: str | Path, device: str | None = None, max_length: int = 256):
        self.model_dir = Path(model_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(self.model_dir)
        self.max_length = max_length

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()

        raw_map = self.model.config.id2label
        self.id2label = {int(k): v for k, v in raw_map.items()} if isinstance(next(iter(raw_map.keys())), str) else raw_map

    def _encode_words_manual(self, words: List[str]):
        input_ids = []

        if self.tokenizer.cls_token_id is not None:
            input_ids.append(self.tokenizer.cls_token_id)
        elif self.tokenizer.bos_token_id is not None:
            input_ids.append(self.tokenizer.bos_token_id)

        first_token_positions = []
        sep_id = self.tokenizer.sep_token_id if self.tokenizer.sep_token_id is not None else self.tokenizer.eos_token_id
        pad_id = self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else 1
        max_body_len = self.max_length - 1

        for word in words:
            sub_ids = self.tokenizer.encode(word, add_special_tokens=False)
            if not sub_ids:
                sub_ids = [self.tokenizer.unk_token_id] if self.tokenizer.unk_token_id is not None else []
            if not sub_ids:
                first_token_positions.append(None)
                continue

            if len(input_ids) + len(sub_ids) > max_body_len:
                break

            first_token_positions.append(len(input_ids))
            input_ids.extend(sub_ids)

        if sep_id is not None and len(input_ids) < self.max_length:
            input_ids.append(sep_id)

        attention_mask = [1] * len(input_ids)

        if len(input_ids) < self.max_length:
            pad_len = self.max_length - len(input_ids)
            input_ids += [pad_id] * pad_len
            attention_mask += [0] * pad_len

        return (
            torch.tensor([input_ids[:self.max_length]], dtype=torch.long, device=self.device),
            torch.tensor([attention_mask[:self.max_length]], dtype=torch.long, device=self.device),
            first_token_positions,
        )

    def _predict_words(self, words: List[str]) -> List[str]:
        input_ids, attention_mask, first_positions = self._encode_words_manual(words)

        with torch.no_grad():
            logits = self.model(input_ids=input_ids, attention_mask=attention_mask).logits
            pred_ids = torch.argmax(logits, dim=-1).squeeze(0).detach().cpu().tolist()

        tags = []
        for pos in first_positions:
            if pos is None or pos >= len(pred_ids):
                tags.append("O")
            else:
                tags.append(self.id2label.get(int(pred_ids[pos]), "O"))
        return tags

    @staticmethod
    def _bio_to_entities(words: List[str], offsets: List[Tuple[int, int]], tags: List[str]) -> List[dict]:
        entities = []
        cur = None

        for word, (s, e), tag in zip(words, offsets, tags):
            if tag.startswith("B-"):
                if cur:
                    entities.append(cur)
                cur = {"text": word, "label": tag[2:], "start": s, "end": e}
            elif tag.startswith("I-") and cur and cur["label"] == tag[2:]:
                cur["text"] += " " + word
                cur["end"] = e
            else:
                if cur:
                    entities.append(cur)
                cur = None

        if cur:
            entities.append(cur)
        return entities

    def predict(self, text: str) -> List[dict]:
        words, offsets = split_words_with_offsets(text)
        if not words:
            return []

        all_entities = []
        chunk_size = self.max_length - 2

        for start_word in range(0, len(words), chunk_size):
            end_word = min(start_word + chunk_size, len(words))
            chunk_words = words[start_word:end_word]
            chunk_offsets = offsets[start_word:end_word]

            tags = self._predict_words(chunk_words)
            ents = self._bio_to_entities(chunk_words, chunk_offsets, tags)
            all_entities.extend(ents)

        return all_entities


def main():
    parser = argparse.ArgumentParser(description="Predict NER bản án ma túy")
    parser.add_argument("--model-dir", type=Path, default=Path("models/phobert-drug-ner/model-best"))
    parser.add_argument("--text", type=str, default=None)
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--max-len", type=int, default=256)
    args = parser.parse_args()

    predictor = NERPredictor(args.model_dir, max_length=args.max_len)

    if args.text:
        text = args.text
    elif args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = (
            "Khoảng 13 giờ ngày 07/10/2025, tại tổ dân phố 10, phường Điện Biên Phủ, "
            "Mùa A T bị bắt quả tang tàng trữ ma túy loại Methamphetamine, khối lượng 1,91 gam. "
            "Căn cứ điểm c khoản 1 Điều 249; Điều 38 Bộ luật Hình sự. "
            "Tuyên bố bị cáo Mùa A T phạm tội “Tàng trữ trái phép chất ma túy”. "
            "Xử phạt bị cáo Mùa A T 03 năm 06 tháng tù."
        )

    entities = predictor.predict(text)
    print(json.dumps(entities, ensure_ascii=False, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
