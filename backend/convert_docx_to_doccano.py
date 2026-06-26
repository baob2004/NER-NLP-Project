from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from docx import Document


DEFAULT_INPUT_DIR = Path("../data/snippets_raw")
DEFAULT_OUTPUT_DIR = Path("../data/processed")


SECTION_NER_TARGETS = {
    "noi_dung": ["DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"],
    "nhan_dinh": ["DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"],
    "quyet_dinh": ["PERSON", "CHARGE", "LEGAL_ARTICLE", "SENTENCE"],
    "negative": [],
    "unknown": [],
}


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)

    replacements = [
        ("\u00a0", " "),
        ("\u200b", ""),
        ("\u200c", ""),
        ("\u200d", ""),
        ("\ufeff", ""),
        ("\ufffe", " "),
        ("\ufffd", ""),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
    ]
    for bad, good in replacements:
        text = text.replace(bad, good)

    fixes = {
        "mat úy": "ma túy",
        "ma tuý": "ma túy",
        "chấtma": "chất ma",
        "bịcáo": "bị cáo",
        "Tuyênbố": "Tuyên bố",
        "Xửphạt": "Xử phạt",
    }
    for bad, good in fixes.items():
        text = text.replace(bad, good)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def normalize_filename_stem(stem: str) -> str:
    return re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()


def strip_diacritics_upper(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("Đ", "D").replace("đ", "d")
    nfd = unicodedata.normalize("NFD", text)
    text = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip().upper()


def is_heading_by_style(style_name: str) -> bool:
    return bool(re.match(r"Heading\s*\d|Title|Subtitle", style_name or "", re.IGNORECASE))


HEADING_LINE_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    (
        "noi_dung",
        "positive",
        re.compile(
            r"^NỘI\s+DUNG\s+VỤ\s+ÁN\s*(?:[-–—:]\s*)?(?:POSITIVE|ĐOẠN\s+GÁN\s+NHÃN)?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "nhan_dinh",
        "positive",
        re.compile(
            r"^NHẬN\s+ĐỊNH(?:\s+CỦA\s+TÒA\s+ÁN|\s+CỦA\s+HỘI\s+ĐỒNG\s+XÉT\s+XỬ)?\s*(?:[-–—:]\s*)?(?:POSITIVE|ĐOẠN\s+GÁN\s+NHÃN)?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "negative",
        "negative",
        re.compile(
            r"^NGỮ\s+CẢNH\s+KHÔNG\s+GÁN\s+NHÃN\s*(?:[-–—:]\s*)?(?:NEGATIVE)?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "quyet_dinh",
        "positive",
        re.compile(
            r"^QUYẾT\s+ĐỊNH\s*(?:[-–—:]\s*)?(?:POSITIVE)?\s*$",
            re.IGNORECASE,
        ),
    ),
]

HEADING_PREFIX_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    (
        "quyet_dinh",
        "positive",
        re.compile(r"^QUYẾT\s+ĐỊNH\s*[:\-–—]?\s+(.+)$", re.IGNORECASE | re.DOTALL),
    ),
    (
        "noi_dung",
        "positive",
        re.compile(
            r"^NỘI\s+DUNG\s+VỤ\s+ÁN\s*(?:[-–—:]\s*)?(?:POSITIVE|ĐOẠN\s+GÁN\s+NHÃN)?\s+(.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "nhan_dinh",
        "positive",
        re.compile(
            r"^NHẬN\s+ĐỊNH(?:\s+CỦA\s+TÒA\s+ÁN|\s+CỦA\s+HỘI\s+ĐỒNG\s+XÉT\s+XỬ)?\s*(?:[-–—:]\s*)?(?:POSITIVE|ĐOẠN\s+GÁN\s+NHÃN)?\s+(.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "negative",
        "negative",
        re.compile(
            r"^NGỮ\s+CẢNH\s+KHÔNG\s+GÁN\s+NHÃN\s*(?:[-–—:]\s*)?(?:NEGATIVE)?\s+(.+)$",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
]


def detect_heading_line(text: str) -> Optional[Tuple[str, str]]:
    t = clean(text)
    for section, split, pat in HEADING_LINE_PATTERNS:
        if pat.fullmatch(t):
            return section, split
    return None


def split_heading_prefix(text: str) -> Tuple[Optional[Tuple[str, str]], str]:
    t = clean(text)

    if re.match(
        r"^NỘI\s+DUNG\s+VỤ\s+ÁN\s+Theo\s+các\s+tài\s+liệu",
        t,
        flags=re.IGNORECASE,
    ):
        return None, t

    for section, split, pat in HEADING_PREFIX_PATTERNS:
        m = pat.match(t)
        if m:
            rest = clean(m.group(1))
            return (section, split), rest

    return None, t


def should_skip_text(text: str) -> bool:
    text = clean(text)
    if not text:
        return True

    if re.fullmatch(r"\d{1,3}", text):
        return True

    skip_patterns = [
        r"^(NỘI\s+DUNG\s+VỤ\s+ÁN\s+)?Theo\s+các\s+tài\s+liệu\s+có\s+trong\s+hồ\s+sơ\s+vụ\s+án.*nội\s+dung\s+vụ\s+án\s+được\s+tóm\s+tắt\s+như\s+sau[:.]?$",
        r"^Trên\s+cơ\s+sở\s+nội\s+dung\s+vụ\s+án,\s*căn\s+cứ\s+vào\s+các\s+tài\s+liệu.*$",
        r"^Hội\s+đồng\s+xét\s+xử\s+nhận\s+định\s+như\s+sau[:.]?$",
        r"^Có\s+đủ\s+cơ\s+sở\s+kết\s+luận[:.]?$",
        r"^Có\s+đủ\s+căn\s+cứ\s+kết\s+luận[:.]?$",
        r"^Hội\s+đồng\s+xét\s+xử\s+có\s+đủ\s+cơ\s+sở\s+kết\s+luận[:.]?$",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in skip_patterns)


SENT_SPLIT_RE = re.compile(
    r"(?<=[.!?;:])\s+(?=[A-ZĐÁÀẢÃẠĂẮẰẶÂẤẦẬÉÈẸẺẼÊẾỀỆÍÌỊÓÒỌÔỐỒỘƠỚỜỢÚÙỤƯỨỪỰÝỲỴ0-9])"
)


def split_long_paragraph(text: str, max_words: int = 240) -> List[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]

    sentences = [s.strip() for s in SENT_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) <= 1:
        return [" ".join(words[i : i + max_words]).strip() for i in range(0, len(words), max_words)]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent.split())
        if current and current_len + sent_len > max_words:
            chunks.append(" ".join(current).strip())
            current = [sent]
            current_len = sent_len
        else:
            current.append(sent)
            current_len += sent_len

    if current:
        chunks.append(" ".join(current).strip())

    return chunks


def iter_records(docx_path: Path, max_words: int = 240) -> Iterator[dict]:
    doc = Document(str(docx_path))
    source = normalize_filename_stem(docx_path.stem)

    current_section = "unknown"
    current_split = "positive"
    record_idx = 0

    for para_idx, para in enumerate(doc.paragraphs):
        raw = "".join(run.text for run in para.runs)
        text = clean(raw)
        if not text:
            continue

        style = para.style.name if para.style else ""

        heading = detect_heading_line(text)
        if heading:
            current_section, current_split = heading
            continue

        if is_heading_by_style(style):
            continue

        prefixed_heading, rest_text = split_heading_prefix(text)
        if prefixed_heading:
            current_section, current_split = prefixed_heading
            text = rest_text

        if should_skip_text(text):
            continue

        section = current_section
        split = current_split

        if section == "negative" or split == "negative":
            section = "negative"
            split = "negative"
            ner_targets: List[str] = []
        else:
            ner_targets = SECTION_NER_TARGETS.get(section, [])

        for chunk in split_long_paragraph(text, max_words=max_words):
            chunk = clean(chunk)
            if should_skip_text(chunk):
                continue

            record_idx += 1
            yield {
                "text": chunk,
                "labels": [],
                "meta": {
                    "source": source,
                    "section": section,
                    "split": split,
                    "ner_targets": ner_targets,
                    "para_idx": para_idx,
                    "record_idx": record_idx,
                },
            }

def get_new_processed_output_path_or_skip(output_dir: Path, filename: str) -> Optional[Path]:
    main_path = output_dir / filename

    if main_path.exists():
        return None

    new_dir = output_dir / "new"
    new_dir.mkdir(parents=True, exist_ok=True)

    candidate = new_dir / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    idx = 1
    while True:
        numbered = new_dir / f"{stem}_{idx}{suffix}"
        if not numbered.exists():
            return numbered
        idx += 1

def convert_docx(docx_path: Path, output_dir: Path, max_words: int = 240) -> Optional[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    out_stem = normalize_filename_stem(docx_path.stem)
    filename = f"{out_stem}.jsonl"

    out_path = get_new_processed_output_path_or_skip(output_dir, filename)

    if out_path is None:
        print(f"  [SKIP] {docx_path.name} → đã có trong {output_dir / filename}")
        return None

    records = list(iter_records(docx_path, max_words=max_words))
    if not records:
        raise ValueError(f"Không tìm thấy đoạn văn nào trong: {docx_path.name}")

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return out_path


def merge_jsonl(jsonl_paths: List[Path], out_path: Path) -> int:
    total = 0
    with open(out_path, "w", encoding="utf-8", newline="\n") as fout:
        for jp in sorted(jsonl_paths):
            with open(jp, encoding="utf-8") as fin:
                for line in fin:
                    line = line.strip()
                    if not line:
                        continue
                    fout.write(line + "\n")
                    total += 1
    return total


def iter_docx(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".docx":
        return [input_path]
    return sorted(input_path.glob("**/*.docx"))


def print_label_help(import_file: Path) -> None:
    print(f"""
─────────────────────────────────────────────────
Import vào Doccano:
  1. Project type: Sequence Labeling
  2. Dataset → Import Dataset
  3. Format: JSONL
  4. File: {import_file}

Label set cần tạo trong Doccano:
  PERSON        – tên bị cáo
  DRUG          – tên/loại chất ma túy cụ thể
  DRUG_WEIGHT   – khối lượng ma túy, chỉ lấy số + đơn vị
  CRIME_TIME    – thời gian phạm tội/bị bắt quả tang cụ thể
  CRIME_LOC     – địa điểm phạm tội/bị bắt quả tang/giao nhận có tên hoặc địa chỉ rõ
  CHARGE        – tội danh Tòa án tuyên
  LEGAL_ARTICLE – điều luật BLHS áp dụng
  SENTENCE      – mức hình phạt chính/bổ sung

Lưu ý:
  - Các record meta.split = "negative" để trống nhãn.
  - Không gán nơi cư trú, ngày cáo trạng, ngày giám định, test nước tiểu,
    án phí, vật chứng, quyền kháng cáo.
─────────────────────────────────────────────────
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chuyển DOCX đã lọc positive/negative sang JSONL chuẩn Doccano."
    )
    parser.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-merge", action="store_true", help="Xuất từng file riêng, không gộp all_cases.jsonl.")
    parser.add_argument("--max-words", type=int, default=240, help="Tách paragraph nếu dài hơn số từ này.")
    args = parser.parse_args()

    docx_files = iter_docx(args.input)
    if not docx_files:
        raise SystemExit(f"Không tìm thấy DOCX trong: {args.input}")

    print(f"Tìm thấy {len(docx_files)} file DOCX → output: {args.output}\n")

    ok_paths: List[Path] = []
    failed = []

    for docx_path in docx_files:
        try:
            out = convert_docx(docx_path, args.output, max_words=args.max_words)

            if out is None:
                continue

            with open(out, encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]

            n_pos = sum(1 for r in records if r.get("meta", {}).get("split") == "positive")
            n_neg = sum(1 for r in records if r.get("meta", {}).get("split") == "negative")
            by_section = {}
            for r in records:
                sec = r.get("meta", {}).get("section", "unknown")
                by_section[sec] = by_section.get(sec, 0) + 1

            print(
                f"  [OK]   {docx_path.name} → {out.name} "
                f"({len(records)} đoạn: {n_pos} positive, {n_neg} negative, section={by_section})"
            )
            ok_paths.append(out)
        except Exception as e:
            print(f"  [FAIL] {docx_path.name}: {e}")
            failed.append((docx_path.name, str(e)))

    if not args.no_merge and len(ok_paths) > 1:
        merged = args.output / "all_cases.jsonl"
        total = merge_jsonl(ok_paths, merged)
        print(f"\n  [MERGE] {merged.name} ({total} đoạn tổng cộng)")

    print(f"\nHoàn tất: {len(ok_paths)}/{len(docx_files)} thành công.")

    if failed:
        print("\nCác file lỗi:")
        for name, err in failed:
            print(f"  - {name}: {err}")

    if ok_paths:
        import_file = args.output / "all_cases.jsonl" if (not args.no_merge and len(ok_paths) > 1) else ok_paths[0]
        print_label_help(import_file)


if __name__ == "__main__":
    main()
