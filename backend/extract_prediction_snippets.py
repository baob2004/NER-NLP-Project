from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import fitz


DEFAULT_INPUT_DIR = Path("../data/raw_judgments")
DEFAULT_OUTPUT_DIR = Path("../data/predict_snippets")

SECTION_NER_TARGETS = {
    "noi_dung": ["DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"],
    "nhan_dinh": ["DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"],
    "quyet_dinh": ["PERSON", "CHARGE", "LEGAL_ARTICLE", "SENTENCE"],
}


def nfc(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    replacements = [
        ("\u00a0", " "),
        ("\u200b", ""),
        ("\u200c", ""),
        ("\u200d", ""),
        ("\ufeff", ""),
        ("\ufffe", " "),
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
        "bịcáo": "bị cáo",
        "Bịcáo": "Bị cáo",
        "Tuyênbố": "Tuyên bố",
        "Xửphạt": "Xử phạt",
        "chấtma": "chất ma",
        "matúy": "ma túy",
        "ma tuý": "ma túy",
        "tàngtrữ": "tàng trữ",
        "tráiphép": "trái phép",
        "Bộluật": "Bộ luật",
        "Hìnhsự": "Hình sự",
        "Tốtụng": "Tố tụng",
    }
    for a, b in fixes.items():
        text = text.replace(a, b)

    text = re.sub(r"[ \t]+", " ", text)
    return text


def strip_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("Đ", "D").replace("đ", "d")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").upper()


def clean_raw(text: str) -> str:
    text = nfc(text)
    lines: List[str] = []

    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,3}", s):
            continue
        if re.fullmatch(r"[-–—_\s]{3,}", s):
            continue
        if s.lower() in {"cộng hòa xã hội chủ nghĩa việt nam", "độc lập - tự do - hạnh phúc"}:
            continue
        lines.append(line.rstrip())

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages = [page.get_text("text", sort=True) for page in doc]
    return clean_raw("\n".join(pages))


CONTENT_HEADS = [
    r"NOI\s+DUNG\s+VU\s+AN\s*:?:?",
    r"TOM\s+TAT\s+NOI\s+DUNG\s+VU\s+AN\s*:?:?",
]

ND_HEADS = [
    r"NHAN\s+DINH\s+CUA\s+TOA\s+AN",
    r"NHAN\s+DINH\s+CUA\s+HOI\s+DONG\s+XET\s+XU",
    r"HOI\s+DONG\s+XET\s+XU\s+NHAN\s+DINH",
    r"TOA\s+AN\s+NHAN\s+DINH",
    r"XET\s+THAY\s*:",
]

QD_HEADS = [
    r"(?m)^\s*QUYET\s+DINH\s*:?\s*$",
    r"(?m)^\s*QUYET\s+DINH\s*:",
]

QD_STOP = [

    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*(?:VE\s+)?XU\s+LY\s+VAT\s+CHUNG",
    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*(?:VE\s+)?VAT\s+CHUNG",
    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*(?:VE\s+)?BIEN\s+PHAP\s+TU\s+PHAP",
    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*(?:VE\s+)?AN\s+PHI",
    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*(?:VE\s+)?QUYEN\s+KHANG\s+CAO",
    r"(?m)(?<![\w\d])\s*[3-9]\s*[\.\)]\s*THONG\s+BAO\s+QUYEN\s+KHANG\s+CAO",

    r"(?m)^\s*NOI\s+NHAN\s*:",
    r"(?m)^\s*TM\.\s*HOI\s+DONG\s+XET\s+XU",
    r"(?m)^\s*T/M\.\s*HOI\s+DONG\s+XET\s+XU",
    r"(?m)^\s*THAM\s+PHAN",
    r"(?m)^\s*\(DA\s+KY\)",
    r"(?m)^-{1,}\s*TAND",
    r"(?m)^-{1,}\s*VKS",
    r"(?m)^-{1,}\s*BI\s+CAO",
    r"(?m)^-{1,}\s*LUU",
]


def first_pos(norm_text: str, patterns: Iterable[str], start: int = 0) -> Optional[int]:
    best = None
    for pat in patterns:
        m = re.search(pat, norm_text[start:], re.IGNORECASE | re.MULTILINE)
        if m:
            pos = start + m.start()
            if best is None or pos < best:
                best = pos
    return best


def locate_sections(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    norm = strip_diacritics(text)
    content_pos = first_pos(norm, CONTENT_HEADS)
    nd_pos = first_pos(norm, ND_HEADS)
    qd_start = (nd_pos + 200) if nd_pos is not None else 0
    qd_pos = first_pos(norm, QD_HEADS, start=qd_start)
    return content_pos, nd_pos, qd_pos


SECTION_TITLE_RE = re.compile(
    r"^\s*(?:NỘI\s+DUNG\s+VỤ\s+ÁN|NHẬN\s+ĐỊNH\s+CỦA\s+TÒA\s+ÁN"
    r"|NHẬN\s+ĐỊNH\s+CỦA\s+HỘI\s+ĐỒNG\s+XÉT\s+XỬ|XÉT\s+THẤY"
    r"|QUYẾT\s+ĐỊNH)\s*:?\s*$",
    re.IGNORECASE,
)

DRUG_HINT_RE = re.compile(
    r"\b(?:ma\s*túy|ma\s*tuý|chất\s+ma\s*túy|Methamphetamine|Heroine|Heroin|Ketamine|MDMA|"
    r"Cần\s+sa|cần\s+sa|thảo\s+mộc\s+khô|hồng\s+phiến|thuốc\s+lắc|nước\s+vui|ma\s*túy\s+đá|hàng\s+khay)\b",
    re.IGNORECASE,
)

WEIGHT_HINT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:gam|gram|g|kg|kilogam|miligam|milligram|mg)\b",
    re.IGNORECASE,
)

TIME_HINT_RE = re.compile(
    r"\b(?:Khoảng|Vào\s+khoảng|Vào\s+lúc|Hồi|Đến\s+khoảng|Ngày|Sáng\s+ngày|"
    r"Trưa\s+ngày|Chiều\s+ngày|Tối\s+ngày)\b|\b\d{1,2}\s*(?:giờ|h)\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.IGNORECASE,
)

LOC_HINT_RE = re.compile(
    r"\b(?:tại|ở|khu\s+vực|địa\s+chỉ|phòng|nhà\s+trọ|nhà\s+nghỉ|khách\s+sạn|"
    r"quán|đường|phố|thôn|xóm|bản|ấp|tổ|khu\s+phố|xã|phường|huyện|quận|"
    r"thành\s+phố|tỉnh|ngã\s+ba|ngã\s+tư)\b",
    re.IGNORECASE,
)

ACTION_HINT_RE = re.compile(
    r"\b(?:mua|bán|giao|nhận|cất\s+giấu|cất\s+giữ|tàng\s+trữ|vận\s+chuyển|"
    r"sử\s+dụng|tổ\s+chức\s+sử\s+dụng|bắt\s+quả\s+tang|kiểm\s+tra|phát\s+hiện|thu\s+giữ|khám\s+xét)\b",
    re.IGNORECASE,
)

ND_DROP_RE = re.compile(
    r"\b(?:Viện\s+kiểm\s+sát|Kiểm\s+sát\s+viên|bản\s+cáo\s+trạng|truy\s+tố|luận\s+tội|"
    r"vật\s+chứng|án\s+phí|kháng\s+cáo|tình\s+tiết\s+tăng\s+nặng|tình\s+tiết\s+giảm\s+nhẹ|"
    r"thành\s+khẩn|ăn\s+năn|hối\s+cải|Nghị\s+quyết\s+326|Điều\s+106\s+Bộ\s+luật\s+Tố\s+tụng)\b",
    re.IGNORECASE,
)

ND_KEEP_RE = re.compile(
    r"\b(?:có\s+đủ\s+căn\s+cứ\s+kết\s+luận|đủ\s+cơ\s+sở\s+kết\s+luận|"
    r"đã\s+có\s+hành\s+vi|hành\s+vi\s+nêu\s+trên|phạm\s+vào\s+tội)\b",
    re.IGNORECASE,
)


def normalize_paragraph(block: str) -> str:
    lines = []
    for line in block.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d{1,3}", s):
            continue
        if SECTION_TITLE_RE.match(s):
            continue
        lines.append(s)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def split_to_paragraphs(text: str, *, split_long: bool = True) -> List[str]:
    paras: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        para = normalize_paragraph(block)
        if not para:
            continue
        if split_long and len(para.split()) > 140:
            parts = [
                p.strip()
                for p in re.split(
                    r"\s+(?=(?:Khoảng|Vào khoảng|Vào lúc|Hồi|Đến khoảng|Ngày|Tại|Sau đó|Đến ngày|Tại bản|Tại Kết luận)\b)",
                    para,
                )
                if p.strip()
            ]
            paras.extend(parts if parts else [para])
        else:
            paras.append(para)
    return paras


def is_relevant_noi_dung_para(text: str, mode: str) -> bool:
    if mode == "raw":
        return True
    if DRUG_HINT_RE.search(text) or WEIGHT_HINT_RE.search(text):
        return True
    if ACTION_HINT_RE.search(text) and (TIME_HINT_RE.search(text) or LOC_HINT_RE.search(text)):
        return True
    return False


def is_relevant_nhan_dinh_para(text: str) -> bool:
    if ND_KEEP_RE.search(text):
        return True
    if ND_DROP_RE.search(text):
        return False
    if DRUG_HINT_RE.search(text) or WEIGHT_HINT_RE.search(text):
        return True
    if ACTION_HINT_RE.search(text) and (TIME_HINT_RE.search(text) or LOC_HINT_RE.search(text)):
        return True
    return False


def filter_quyet_dinh(text: str) -> str:
    lines = []

    for line in text.splitlines():
        s = line.strip()

        if not s:
            continue

        if re.fullmatch(r"\d{1,3}", s):
            continue

        lines.append(s)

    raw = "\n".join(lines).strip()

    raw = re.sub(
        r"^\s*QUYẾT\s+ĐỊNH\s*:?\s*",
        "",
        raw,
        flags=re.IGNORECASE
    ).strip()

    norm = strip_diacritics(raw)
    stop = len(raw)

    for pat in QD_STOP:
        m = re.search(pat, norm, re.IGNORECASE | re.MULTILINE)
        if m and m.start() < stop:
            stop = m.start()

    kept = raw[:stop].strip()

    kept = re.sub(r"[ \t]+", " ", kept)
    kept = re.sub(r"\n+", " ", kept).strip()

    parts = [
        p.strip()
        for p in re.split(r"(?=\b\d{1,2}\s*[\.\)]\s+)", kept)
        if p.strip()
    ]

    final_parts = []

    for p in parts:
        p_norm = strip_diacritics(p)

        if not re.match(r"^\s*\d{1,2}\s*[\.\)]", p):
            final_parts.append(p)
            continue

        if re.match(r"^\s*[12]\s*[\.\)]", p):
            final_parts.append(p)
            continue

        if re.match(r"^\s*[3-9]\s*[\.\)]", p):
            continue

    return "\n\n".join(final_parts).strip()


def extract_sections(full_text: str, content_mode: str = "raw") -> List[dict]:
    text = clean_raw(full_text)
    content_pos, nd_pos, qd_pos = locate_sections(text)
    content_raw = ""
    nd_raw = ""
    qd_raw = ""
    if content_pos is not None and nd_pos is not None and nd_pos > content_pos:
        content_raw = text[content_pos:nd_pos]
    elif content_pos is not None:
        content_raw = text[content_pos:qd_pos or len(text)]
    if nd_pos is not None:
        nd_raw = text[nd_pos:qd_pos or len(text)]
    if qd_pos is not None:
        qd_raw = text[qd_pos:]

    records: List[dict] = []
    for para in split_to_paragraphs(content_raw):
        if is_relevant_noi_dung_para(para, content_mode):
            records.append({"section": "noi_dung", "text": para})
    for para in split_to_paragraphs(nd_raw):
        if is_relevant_nhan_dinh_para(para):
            records.append({"section": "nhan_dinh", "text": para})
    qd_clean = filter_quyet_dinh(qd_raw) if qd_raw else ""
    for para in split_to_paragraphs(qd_clean, split_long=False):
        records.append({"section": "quyet_dinh", "text": para})
    return records


def build_predict_records(pdf_path: Path, content_mode: str = "raw") -> List[dict]:
    full_text = extract_pdf_text(pdf_path)
    source = re.sub(r"\(\d+\)$", "", pdf_path.stem).strip()
    section_records = extract_sections(full_text, content_mode=content_mode)
    output: List[dict] = []
    for idx, item in enumerate(section_records, start=1):
        section = item["section"]
        output.append({
            "id": f"{source}::{idx:04d}",
            "text": item["text"],
            "labels": [],
            "meta": {
                "source": source,
                "section": section,
                "ner_targets": SECTION_NER_TARGETS.get(section, []),
                "para_idx": idx,
            },
        })
    return output


def save_jsonl(records: List[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def process_pdf(pdf_path: Path, output_dir: Path, content_mode: str = "raw") -> Path:
    records = build_predict_records(pdf_path, content_mode=content_mode)
    stem = re.sub(r"\(\d+\)$", "", pdf_path.stem).strip()
    out_path = output_dir / f"{stem}.predict.jsonl"
    save_jsonl(records, out_path)
    return out_path


def iter_pdfs(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    return sorted(input_path.glob("*.pdf"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cắt PDF bản án thành JSONL phục vụ predict/pipeline NER ma túy."
    )
    parser.add_argument("--input", "-i", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--content-mode",
        choices=["raw", "filtered"],
        default="raw",
        help="raw: giữ nội dung vụ án gần như nguyên bản; filtered: lọc nhẹ đoạn có tín hiệu ma túy/thời gian/địa điểm.",
    )
    args = parser.parse_args()

    pdfs = iter_pdfs(args.input)
    if not pdfs:
        raise SystemExit(f"Không tìm thấy PDF trong: {args.input}")

    ok = 0
    failed = []
    print(f"Tìm thấy {len(pdfs)} PDF")
    print(f"Output: {args.output}")
    print(f"content-mode: {args.content_mode}\n")

    for pdf in pdfs:
        try:
            out = process_pdf(pdf, args.output, content_mode=args.content_mode)
            n = sum(1 for _ in out.open(encoding="utf-8"))
            print(f"[OK]   {pdf.name} -> {out.name} ({n} đoạn)")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {pdf.name}: {e}")
            failed.append((pdf.name, str(e)))

    print(f"\nHoàn tất: {ok}/{len(pdfs)} file thành công.")
    if failed:
        print("Các file lỗi:")
        for name, err in failed:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
