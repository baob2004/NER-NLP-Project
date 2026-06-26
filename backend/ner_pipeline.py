from __future__ import annotations

import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

try:
    from extract_prediction_snippets import build_predict_records
except Exception as e:
    raise RuntimeError(
        "Không import được extract_prediction_snippets.py. "
        "Hãy đặt extract_prediction_snippets.py cùng thư mục với ner_pipeline.py/api.py. "
        f"Lỗi gốc: {e}"
    )

try:
    from ner_predictor import NERPredictor
except Exception as e:
    raise RuntimeError(
        "Không import được ner_predictor.py hoặc class NERPredictor. "
        "Hãy đặt ner_predictor.py cùng thư mục với ner_pipeline.py/api.py. "
        f"Lỗi gốc: {e}"
    )

BASE = Path(__file__).resolve().parent
DEFAULT_MODELS_ROOT = BASE / "models"
if not DEFAULT_MODELS_ROOT.exists():
    alt = BASE.parent / "models"
    if alt.exists():
        DEFAULT_MODELS_ROOT = alt

MODEL_ROOT = Path(os.environ.get("MODEL_ROOT", str(DEFAULT_MODELS_ROOT)))
DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "phobert")

MODEL_REGISTRY = {
    "phobert": {
        "display_name": "PhoBERT",
        "kind": "transformer",
        "candidates": [
            "phobert-drug-ner/model-best",
            "phobert-drug-ner",
        ],
    },
    "xlmr": {
        "display_name": "XLM-RoBERTa",
        "kind": "transformer",
        "candidates": [
            "xlmr-drug-ner/model-best",
            "xlmr-drug-ner",
        ],
    },
    "spacy": {
        "display_name": "spaCy",
        "kind": "spacy",
        "candidates": [
            "spacy-drug-ner/model-best",
            "spacy-drug-ner",
        ],
    },
}

MODEL_ALIASES = {
    "phoBERT": "phobert",
    "PhoBERT": "phobert",
    "phobert": "phobert",
    "bert": "phobert",
    "xlm": "xlmr",
    "xlmr": "xlmr",
    "xlm-r": "xlmr",
    "xlm_roberta": "xlmr",
    "xlm-roberta": "xlmr",
    "XLM-RoBERTa": "xlmr",
    "spacy": "spacy",
    "spaCy": "spacy",
}


def normalize_model_name(model_name: Optional[str] = None) -> str:
    name = (model_name or DEFAULT_MODEL_NAME or "phobert").strip()
    return MODEL_ALIASES.get(name, name)


def _has_transformer_model(path: Path) -> bool:
    return (
        (path / "config.json").exists()
        and ((path / "model.safetensors").exists() or (path / "pytorch_model.bin").exists())
    )


def _has_spacy_model(path: Path) -> bool:
    return (path / "meta.json").exists() or (path / "config.cfg").exists()


def get_model_info(model_name: Optional[str] = None) -> dict:
    key = normalize_model_name(model_name)
    if key not in MODEL_REGISTRY:
        raise RuntimeError(f"Model không hợp lệ: {model_name}. Chọn một trong: {', '.join(MODEL_REGISTRY)}")

    info = dict(MODEL_REGISTRY[key])
    info["name"] = key

    for rel in info["candidates"]:
        path = MODEL_ROOT / rel
        if info["kind"] == "transformer" and _has_transformer_model(path):
            info["path"] = path
            return info
        if info["kind"] == "spacy" and _has_spacy_model(path):
            info["path"] = path
            return info

    info["path"] = MODEL_ROOT / info["candidates"][0]
    return info


def _default_model_dir() -> Path:
    return get_model_info(DEFAULT_MODEL_NAME)["path"]


MODEL_DIR = _default_model_dir()

ENTITY_TYPES = [
    "PERSON",
    "DRUG",
    "DRUG_WEIGHT",
    "CRIME_TIME",
    "CRIME_LOC",
    "CHARGE",
    "LEGAL_ARTICLE",
    "SENTENCE",
]

SECTION_ENTITY_MAP = {
    "noi_dung": {"DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"},
    "nhan_dinh": {"DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC"},
    "quyet_dinh": {"PERSON", "CHARGE", "LEGAL_ARTICLE", "SENTENCE"},
}

SECTION_RANK = {
    "noi_dung": 0,
    "nhan_dinh": 1,
    "quyet_dinh": 2,
    "unknown": 9,
}

TRIM_CHARS = ' \t\n\r.,;:()[]{}"“”‘’'


def list_available_models() -> List[dict]:
    models = []
    for key in MODEL_REGISTRY:
        info = get_model_info(key)
        path = Path(info["path"])
        ok = _has_transformer_model(path) if info["kind"] == "transformer" else _has_spacy_model(path)
        models.append({
            "name": key,
            "display_name": info["display_name"],
            "kind": info["kind"],
            "path": str(path),
            "available": bool(ok),
            "is_default": key == normalize_model_name(DEFAULT_MODEL_NAME),
        })
    return models


def get_model_dir(model_name: Optional[str] = None) -> Path:
    return get_model_info(model_name)["path"]


def clean_entity_text(entity_text: str) -> str:
    return str(entity_text or "").strip(TRIM_CHARS)


def normalize_drug_name(text: str) -> str:
    s = clean_entity_text(text)
    low = s.lower().replace("“", "").replace("”", "").replace('"', "")
    if "methmphetamine" in low or "methamphetamine" in low or "metamphetamine" in low:
        return "Methamphetamine"
    if low in {"heroin", "heroine"}:
        return "Heroine"
    if "ketamine" in low or "ketamin" in low:
        return "Ketamine"
    if "mdma" in low:
        return "MDMA"
    if "amphetamine" in low and "meth" not in low:
        return "Amphetamine"
    if "cần sa" in low or "can sa" in low or "thảo mộc khô" in low or "thao moc kho" in low:
        return "Cần sa"
    if "hồng phiến" in low or "hong phien" in low:
        return "hồng phiến"
    if "thuốc lắc" in low or "thuoc lac" in low:
        return "thuốc lắc"
    if "nước vui" in low or "nuoc vui" in low:
        return "nước vui"
    if "hàng khay" in low or "khay" in low:
        return "Ketamine"
    if "đá" in low and ("ma" in low or "túy" in low or "tuý" in low):
        return "ma túy đá"
    return s


def normalize_weight(text: str) -> str:
    s = clean_entity_text(text)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\bg\b", "gam", s, flags=re.IGNORECASE)
    s = re.sub(r"\bgram\b", "gam", s, flags=re.IGNORECASE)
    return s


def normalize_legal_article(text: str) -> str:
    return re.sub(r"\s+", " ", clean_entity_text(text))


def normalize_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", clean_entity_text(text))


def normalize_charge(text: str) -> str:
    s = clean_entity_text(text).strip("“”\"'")
    return re.sub(r"\s+", " ", s)


def normalize_person(text: str) -> str:
    s = re.sub(r"\s+", " ", clean_entity_text(text))
    s = re.split(
        r"\s+(?:phạm|về|bị|xử|phải|chịu|chấp|từ|đến)\b",
        s,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return s


def is_valid_weight(text: str) -> bool:
    return bool(re.search(
        r"\b\d+(?:[.,]\d+)?\s*(?:gam|g|mg|kg|gram|miligam|milligram)\b",
        text,
        flags=re.IGNORECASE,
    ))


def is_bad_drug(text: str) -> bool:
    return text.strip() in {"Đ", "Đ2", "D", "D1", "T", "T1", "N", "N1", "K", "H", "H2", "H3"}


def is_bad_drug_context(entity: dict) -> bool:
    ctx = str(entity.get("context") or "").lower()
    return any(k in ctx for k in [
        "mẫu nước tiểu", "nước tiểu", "test nhanh", "xét nghiệm", "danh mục", "nghị định", "stt",
    ])


def is_bad_weight_context(entity: dict) -> bool:
    ctx = str(entity.get("context") or "").lower()
    return any(k in ctx for k in ["hoàn lại", "còn lại sau giám định", "mẫu hoàn", "mẫu vật còn lại"])


def is_bad_legal_article(text: str) -> bool:
    return bool(re.search(
        r"(Điều\s+32|Điều\s+47|Điều\s+106|Điều\s+135|Điều\s+136|"
        r"Điều\s+298|Điều\s+331|Điều\s+333|Nghị\s+quyết\s+326|"
        r"Bộ\s+luật\s+Tố\s+tụng|án\s+phí|vật\s+chứng)",
        text,
        flags=re.IGNORECASE,
    ))


def is_valid_person(text: str) -> bool:
    parts = text.split()
    if len(parts) < 2 or len(parts) > 6:
        return False
    bad_words = {"Tòa", "Viện", "Hội", "Điều", "Bộ", "Căn", "Xử", "Tuyên", "Buộc", "Không", "Miễn", "Tịch", "Trả", "Thời", "Kể"}
    if parts[0] in bad_words:
        return False
    return True


def is_valid_crime_time(text: str) -> bool:
    s = clean_entity_text(text)
    return bool(re.search(
        r"(\d{1,2}\s*(?:giờ|h)|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}|"
        r"Khoảng|Vào\s+khoảng|Hồi|Đến\s+khoảng|Sáng\s+ngày|Trưa\s+ngày|Chiều\s+ngày|Tối\s+ngày)",
        s,
        flags=re.IGNORECASE,
    ))


def is_bad_time_context(entity: dict) -> bool:
    ctx = str(entity.get("context") or "").lower()
    if any(k in ctx for k in ["kết luận giám định", "cáo trạng", "quyết định đưa vụ án", "ngày xét xử", "thụ lý", "mẫu nước tiểu", "xét nghiệm"]):
        if not any(k in ctx for k in ["mua", "bán", "giao", "nhận", "sử dụng", "cất giấu", "tàng trữ", "vận chuyển", "bắt quả tang", "kiểm tra", "thu giữ"]):
            return True
    return False


def is_clear_crime_loc(text: str) -> bool:
    s = clean_entity_text(text)
    low = s.lower()
    if len(s) < 5:
        return False
    vague_exact = {"tại đây", "ở đây", "khu vực này", "khu vực trên", "khu vực nêu trên", "địa điểm trên", "nơi trên", "chỗ đó", "chỗ này", "trên đường"}
    if low in vague_exact:
        return False
    if re.fullmatch(r"(xã|phường|huyện|quận|tỉnh|thành phố)\s+[A-ZĐA-Za-zÀ-ỹ0-9]+", s, flags=re.IGNORECASE):
        return False
    strong_patterns = [
        r"\bsố\s+[A-Z0-9/.-]+", r"\bphòng\s+\w+", r"\bnhà\s+trọ\b", r"\bnhà\s+nghỉ\b", r"\bkhách\s+sạn\b",
        r"\bquán\b", r"\bchợ\b", r"\bđường\b", r"\bphố\b", r"\bngõ\b", r"\bngách\b", r"\bhẻm\b",
        r"\bthôn\b", r"\bxóm\b", r"\bbản\b", r"\bấp\b", r"\btổ\s+dân\s+phố\b", r"\bkhu\s+phố\b", r"\bkhóm\b",
        r"\bngã\s+ba\b", r"\bngã\s+tư\b", r"\bchung\s+cư\b", r"\bkhu\s+đô\s+thị\b", r"\bcổng\b", r"\bbến\s+xe\b", r"\bnghĩa\s+trang\b", r"\bcửa\s+khẩu\b",
    ]
    has_specific = any(re.search(p, low, flags=re.IGNORECASE) for p in strong_patterns)
    admin_count = len(re.findall(r"\b(?:xã|phường|thị\s+trấn|huyện|quận|thành\s+phố|tỉnh)\b", low))
    return bool(has_specific or (admin_count >= 2 and len(s.split()) >= 4))


def is_bad_loc_context(entity: dict) -> bool:
    ctx = str(entity.get("context") or "").lower()
    if any(k in ctx for k in ["nơi thường trú", "hktt", "trú tại", "trụ sở tòa án", "viện kiểm sát", "tòa án nhân dân"]):
        if not any(k in ctx for k in ["mua", "bán", "giao", "nhận", "sử dụng", "cất giấu", "tàng trữ", "vận chuyển", "bắt quả tang", "kiểm tra", "thu giữ"]):
            return True
    return False


def is_valid_sentence(text: str) -> bool:
    s = text.lower()
    if "án phí" in s or "vật chứng" in s:
        return False
    if "tù" in s:
        return True
    if re.search(r"(phạt\s+tiền|phạt\s+bổ\s+sung).*\d{1,3}(?:\.\d{3})+\s*đồng", s):
        return True
    return False


def clean_one_entity(entity: dict) -> Optional[dict]:
    label = str(entity.get("label") or entity.get("entity") or "").strip()
    text = clean_entity_text(entity.get("text") or entity.get("word") or "")
    if not label or label not in ENTITY_TYPES or not text:
        return None
    e = dict(entity)
    e["label"] = label
    e["entity"] = label
    if label == "DRUG":
        text = normalize_drug_name(text)
        if is_bad_drug(text) or is_bad_drug_context(e):
            return None
    elif label == "DRUG_WEIGHT":
        text = normalize_weight(text)
        if not is_valid_weight(text) or is_bad_weight_context(e):
            return None
    elif label == "CRIME_TIME":
        text = clean_entity_text(text)
        if not is_valid_crime_time(text) or is_bad_time_context(e):
            return None
    elif label == "CRIME_LOC":
        text = clean_entity_text(text)
        if not is_clear_crime_loc(text) or is_bad_loc_context(e):
            return None
    elif label == "PERSON":
        text = normalize_person(text)
        if not is_valid_person(text):
            return None
    elif label == "CHARGE":
        text = normalize_charge(text)
        if "chất ma túy" not in text.lower():
            return None
    elif label == "LEGAL_ARTICLE":
        text = normalize_legal_article(text)
        if is_bad_legal_article(text):
            return None
    elif label == "SENTENCE":
        text = normalize_sentence(text)
        if not is_valid_sentence(text):
            return None
    e["text"] = text
    e["word"] = text
    e["score"] = float(e.get("score", 1.0) or 1.0)
    return e


def postprocess_entities(entities: List[dict]) -> List[dict]:
    cleaned = []
    for e in entities:
        item = clean_one_entity(e)
        if item is not None:
            cleaned.append(item)
    return cleaned


NAME_PART = r"[A-ZĐ][a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]+|[A-ZĐ]"
PERSON_CTX_RE = re.compile(rf"\bbị\s+cáo\s+((?:{NAME_PART})(?:\s+(?:{NAME_PART})){{1,5}})", re.IGNORECASE)
PERSON_AFTER_RE = re.compile(rf"(?:Tuyên\s+bố|Xử\s+phạt|Buộc)\s+(?:bị\s+cáo\s+)?((?:{NAME_PART})(?:\s+(?:{NAME_PART})){{1,5}})", re.IGNORECASE)
CHARGE_RE = re.compile(r"(?:Tàng\s+trữ|Mua\s+bán|Vận\s+chuyển|Tổ\s+chức\s+sử\s+dụng|Sử\s+dụng)\s+trái\s+phép\s+chất\s+ma\s+túy", re.IGNORECASE)
LEGAL_RES = [
    re.compile(r"\bđiểm\s+[a-z]\s+khoản\s+\d+\s+Điều\s+\d+[a-z]?\b", re.IGNORECASE),
    re.compile(r"\bkhoản\s+\d+\s+Điều\s+\d+[a-z]?\b", re.IGNORECASE),
    re.compile(r"\bĐiều\s+\d+[a-z]?\b", re.IGNORECASE),
]
SENTENCE_RES = [
    re.compile(r"(?:Xử\s+phạt|xử\s+phạt|phạt)\s+(?:bị\s+cáo\s+)?[A-ZĐ][^.;:\n]{0,90}?\s+(?:\d{1,2}|[a-zà-ỹ\s]+)\s*(?:\([^)]*\)\s*)?(?:năm|tháng)\s+(?:\d{1,2}\s*(?:\([^)]*\)\s*)?tháng\s+)?tù", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s*(?:\([^)]*\)\s*)?năm(?:\s+\d{1,2}\s*(?:\([^)]*\)\s*)?tháng)?\s+tù\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s*(?:\([^)]*\)\s*)?tháng\s+tù\b", re.IGNORECASE),
    re.compile(r"phạt\s+(?:bổ\s+sung\s+)?(?:bị\s+cáo\s+)?[A-ZĐ][^.;:\n]{0,80}?\s+\d{1,3}(?:\.\d{3})+\s*đồng", re.IGNORECASE),
    re.compile(r"phạt\s+tiền\s+\d{1,3}(?:\.\d{3})+\s*đồng", re.IGNORECASE),
]


def add_entity(out: List[dict], *, label: str, text: str, start: int, end: int, section: str, source: str, record_idx: int, context: str, rule_name: str) -> None:
    item = {
        "label": label, "entity": label, "text": text, "word": text, "score": 1.0,
        "start": start, "end": end, "section": section, "source": source,
        "record_idx": record_idx, "unit_idx": record_idx, "context": context,
        "rule_based": True, "rule_name": rule_name,
    }
    cleaned = clean_one_entity(item)
    if cleaned is not None:
        out.append(cleaned)


def add_rule_based_decision_entities(entities: List[dict], records: List[dict], source: str) -> List[dict]:
    out = list(entities)
    for rec_idx, rec in enumerate(records):
        meta = rec.get("meta", {}) or {}
        section = meta.get("section", "unknown")
        if section != "quyet_dinh":
            continue
        text = rec.get("text", "")
        context = text[:500]
        for rex in [PERSON_CTX_RE, PERSON_AFTER_RE]:
            for m in rex.finditer(text):
                name = m.group(1).strip()
                name = re.split(r"\s+(?:phạm|về|bị|xử|phải|chịu|chấp|từ|đến)\b", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                add_entity(out, label="PERSON", text=name, start=m.start(1), end=m.start(1) + len(name), section=section, source=source, record_idx=rec_idx, context=context, rule_name="decision_person")
        for m in CHARGE_RE.finditer(text):
            add_entity(out, label="CHARGE", text=m.group(0), start=m.start(), end=m.end(), section=section, source=source, record_idx=rec_idx, context=context, rule_name="decision_charge")
        for rex in LEGAL_RES:
            for m in rex.finditer(text):
                add_entity(out, label="LEGAL_ARTICLE", text=m.group(0), start=m.start(), end=m.end(), section=section, source=source, record_idx=rec_idx, context=context, rule_name="decision_legal_article")
        for rex in SENTENCE_RES:
            for m in rex.finditer(text):
                add_entity(out, label="SENTENCE", text=m.group(0), start=m.start(), end=m.end(), section=section, source=source, record_idx=rec_idx, context=context, rule_name="decision_sentence")
    return out


def deduplicate_entities(entities: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for e in entities:
        key = (e.get("section"), e.get("record_idx"), e.get("label"), e.get("text"), e.get("start"), e.get("end"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def sort_entities(entities: List[dict]) -> List[dict]:
    entities.sort(key=lambda e: (
        SECTION_RANK.get(e.get("section", "unknown"), 9),
        int(e.get("record_idx", e.get("unit_idx", 999999)) or 999999),
        int(e.get("start", 999999) or 999999),
        1 if e.get("rule_based") else 0,
    ))
    for i, e in enumerate(entities):
        e["order"] = i
    return entities


def predict_records(predictor: NERPredictor, records: List[dict], source: str) -> List[dict]:
    entities = []
    for rec_idx, rec in enumerate(records):
        text = rec.get("text", "")
        meta = rec.get("meta", {}) or {}
        section = meta.get("section", "unknown")
        allowed = set(meta.get("ner_targets") or SECTION_ENTITY_MAP.get(section, set()))
        if not text.strip() or not allowed:
            continue
        predicted = predictor.predict(text)
        for e in predicted:
            label = e.get("label") or e.get("entity") or ""
            if label not in allowed:
                continue
            item = dict(e)
            item["label"] = label
            item["entity"] = label
            item["source"] = source
            item["section"] = section
            item["record_idx"] = rec_idx
            item["unit_idx"] = rec_idx
            item["context"] = text[:500]
            item["rule_based"] = False
            item["record_id"] = rec.get("id")
            entities.append(item)
    entities = postprocess_entities(entities)
    entities = add_rule_based_decision_entities(entities, records, source)
    entities = postprocess_entities(entities)
    entities = deduplicate_entities(entities)
    return sort_entities(entities)


def build_sections(records: List[dict]) -> Dict[str, str]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for rec in records:
        meta = rec.get("meta", {}) or {}
        section = meta.get("section", "unknown")
        text = rec.get("text", "").strip()
        if text:
            grouped[section].append(text)
    return {
        "noi_dung": "\n\n".join(grouped.get("noi_dung", [])),
        "nhan_dinh": "\n\n".join(grouped.get("nhan_dinh", [])),
        "quyet_dinh": "\n\n".join(grouped.get("quyet_dinh", [])),
    }


def build_filtered_text(sections: Dict[str, str]) -> str:
    titles = {"noi_dung": "NỘI DUNG VỤ ÁN", "nhan_dinh": "NHẬN ĐỊNH CỦA TÒA ÁN", "quyet_dinh": "QUYẾT ĐỊNH"}
    parts = []
    for sec in ["noi_dung", "nhan_dinh", "quyet_dinh"]:
        text = sections.get(sec, "")
        if text.strip():
            parts.append(f"{titles[sec]}\n{text.strip()}")
    return "\n\n".join(parts).strip()


def build_entities_by_label(entities_ordered: List[dict]) -> Dict[str, List[dict]]:
    grouped = {k: [] for k in ENTITY_TYPES}
    for e in entities_ordered:
        label = e.get("label") or e.get("entity")
        if label not in grouped:
            continue
        grouped[label].append({
            "word": e.get("text") or e.get("word"),
            "text": e.get("text") or e.get("word"),
            "score": float(e.get("score", 1.0)),
            "section": e.get("section", ""),
            "start": int(e.get("start", 0) or 0),
            "end": int(e.get("end", 0) or 0),
            "record_idx": e.get("record_idx"),
            "unit_idx": e.get("unit_idx"),
            "order": e.get("order"),
            "rule_based": bool(e.get("rule_based", False)),
            "rule_name": e.get("rule_name"),
        })
    return grouped


def build_highlighted(records: List[dict], entities_ordered: List[dict]) -> List[dict]:
    by_record: Dict[int, List[dict]] = defaultdict(list)
    for e in entities_ordered:
        record_idx = e.get("record_idx")
        if record_idx is None:
            continue
        start, end = e.get("start"), e.get("end")
        if start is None or end is None:
            continue
        by_record[int(record_idx)].append({
            "start": int(start), "end": int(end), "entity": e.get("label") or e.get("entity"),
            "word": e.get("text") or e.get("word"), "score": float(e.get("score", 1.0)),
            "order": e.get("order"), "rule_based": bool(e.get("rule_based", False)),
        })
    highlighted = []
    for idx, rec in enumerate(records):
        spans = sorted(by_record.get(idx, []), key=lambda x: (x["start"], x["end"]))
        if not spans:
            continue
        meta = rec.get("meta", {}) or {}
        highlighted.append({"record_idx": idx, "section": meta.get("section", "unknown"), "text": rec.get("text", ""), "spans": spans})
    return highlighted


def build_relationships(entities_ordered: List[dict]) -> List[dict]:
    rels = []
    for i, e in enumerate(entities_ordered):
        label = e.get("label")
        section = e.get("section")
        if label == "PERSON" and section == "quyet_dinh":
            for j in range(i + 1, min(len(entities_ordered), i + 12)):
                t = entities_ordered[j]
                if t.get("section") != "quyet_dinh":
                    continue
                if t.get("label") == "SENTENCE":
                    rels.append({"type": "PERSON_HAS_SENTENCE", "from": e.get("text"), "to": t.get("text"), "source_order": [e.get("order"), t.get("order")]})
                    break
            for j in range(i + 1, min(len(entities_ordered), i + 14)):
                t = entities_ordered[j]
                if t.get("section") != "quyet_dinh":
                    continue
                if t.get("label") == "CHARGE":
                    rels.append({"type": "PERSON_HAS_CHARGE", "from": e.get("text"), "to": t.get("text"), "source_order": [e.get("order"), t.get("order")]})
                    break
        if label == "DRUG":
            candidates = []
            for j in range(max(0, i - 4), min(len(entities_ordered), i + 5)):
                t = entities_ordered[j]
                if t.get("section") != section:
                    continue
                if t.get("label") == "DRUG_WEIGHT":
                    candidates.append(t)
            if candidates:
                w = min(candidates, key=lambda x: abs((x.get("order") or 0) - (e.get("order") or 0)))
                rels.append({"type": "DRUG_HAS_WEIGHT", "from": e.get("text"), "to": w.get("text"), "source_order": [e.get("order"), w.get("order")]})
    return rels


class UnifiedPredictor:

    def __init__(self, model_info: dict):
        self.model_info = model_info
        self.name = model_info["name"]
        self.display_name = model_info["display_name"]
        self.kind = model_info["kind"]
        self.model_dir = Path(model_info["path"])

        if not self.model_dir.exists():
            raise RuntimeError(f"Không tìm thấy model {self.display_name}: {self.model_dir}")

        if self.kind == "transformer":
            self.model = NERPredictor(self.model_dir)
        elif self.kind == "spacy":
            try:
                import spacy
            except Exception as e:
                raise RuntimeError("Chưa cài spaCy. Chạy: pip install spacy") from e
            self.model = spacy.load(self.model_dir)
        else:
            raise RuntimeError(f"Loại model không hỗ trợ: {self.kind}")

    def predict(self, text: str) -> List[dict]:
        if self.kind == "transformer":
            return self.model.predict(text)

        doc = self.model(text)
        out = []
        for ent in doc.ents:
            out.append({
                "label": ent.label_,
                "entity": ent.label_,
                "text": ent.text,
                "word": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "score": 1.0,
            })
        return out


class NERPipeline:

    def __init__(
        self,
        model_dir: Path | None = None,
        model_name: Optional[str] = None,
        model_display_name: Optional[str] = None,
        model_kind: Optional[str] = None,
    ):
        self.predictor_cache: Dict[str, UnifiedPredictor] = {}

        model_key = normalize_model_name(model_name)

        if model_dir is not None:
            model_dir = Path(model_dir)

            inferred_kind = model_kind
            if inferred_kind is None:
                inferred_kind = "spacy" if _has_spacy_model(model_dir) else "transformer"

            inferred_display_name = model_display_name
            if inferred_display_name is None:
                inferred_display_name = MODEL_REGISTRY.get(model_key, {}).get("display_name", model_key)

            info = {
                "name": model_key,
                "display_name": inferred_display_name,
                "kind": inferred_kind,
                "path": model_dir,
            }
        else:
            info = get_model_info(model_key)

            if model_display_name is not None:
                info["display_name"] = model_display_name

            if model_kind is not None:
                info["kind"] = model_kind

        self.model_name = info["name"]
        self.model_display_name = info["display_name"]
        self.model_kind = info["kind"]
        self.model_dir = Path(info["path"])
        self.default_model_name = self.model_name

        print("=" * 80)
        print("NERPipeline multi-model: PhoBERT + XLM-RoBERTa + spaCy")
        print(f"MODEL_ROOT         = {MODEL_ROOT}")
        print(f"MODEL_NAME         = {self.model_name}")
        print(f"MODEL_DISPLAY_NAME = {self.model_display_name}")
        print(f"MODEL_KIND         = {self.model_kind}")
        print(f"MODEL_DIR          = {self.model_dir}")
        print("Available models:")
        for item in list_available_models():
            status = "OK" if item["available"] else "MISSING"
            default = " default" if item["is_default"] else ""
            print(f"- {item['name']}: {item['display_name']} | {item['kind']} | {status}{default} | {item['path']}")
        print("=" * 80)

        first_predictor = UnifiedPredictor(info)
        self.predictor_cache[self.model_name] = first_predictor
        self.predictor = first_predictor

    def get_predictor(self, model_name: Optional[str] = None) -> UnifiedPredictor:
        key = normalize_model_name(model_name or self.default_model_name)

        if key not in self.predictor_cache:
            info = get_model_info(key)
            self.predictor_cache[key] = UnifiedPredictor(info)

        return self.predictor_cache[key]

    def run(
        self,
        pdf_bytes: bytes,
        filename: str = "file.pdf",
        content_mode: str = "raw",
        model_name: Optional[str] = None,
    ) -> dict:
        if content_mode not in {"raw", "filtered"}:
            raise ValueError("content_mode chỉ nhận 'raw' hoặc 'filtered'")

        predictor = self.get_predictor(model_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / filename
            pdf_path.write_bytes(pdf_bytes)
            records = build_predict_records(pdf_path, content_mode=content_mode)

        sections = build_sections(records)
        filtered_text = build_filtered_text(sections)
        entities_ordered = predict_records(predictor, records, source=filename)
        entities = build_entities_by_label(entities_ordered)
        highlighted = build_highlighted(records, entities_ordered)
        relationships = build_relationships(entities_ordered)

        return {
            "filename": filename,
            "model_name": predictor.name,
            "model_display_name": predictor.display_name,
            "model_kind": predictor.kind,
            "model_dir": str(predictor.model_dir),
            "available_models": list_available_models(),
            "content_mode": content_mode,
            "num_records": len(records),
            "records": records,
            "filtered_text": filtered_text,
            "sections": sections,
            "entities": entities,
            "entities_ordered": entities_ordered,
            "highlighted": highlighted,
            "relationships": relationships,
            "counts": {k: len(v) for k, v in entities.items()},
        }
