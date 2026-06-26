# -*- coding: utf-8 -*-
"""
api.py
FastAPI backend cho NER bản án hình sự ma túy.

Flow:
    Upload PDF
    -> ner_pipeline.NERPipeline
    -> extract_prediction_snippets.py cắt đoạn predict
    -> model PhoBERT predict 8 nhãn
    -> lọc nhãn theo section
    -> trả JSON cho frontend

Không dùng pdf_highlighter.
Không xuất PDF highlight.

Chạy:
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import os
import time
import traceback
import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"

# 1. FIX ĐƯỜNG DẪN MODEL: Khóa cứng đường dẫn tuyệt đối trên Hugging Face
MODEL_ROOT = Path("/home/user/app/backend/models")

UPLOAD_DIR = STORAGE_DIR / "uploads"
EXPORT_JSON_DIR = STORAGE_DIR / "exports" / "json"
EXPORT_TXT_DIR = STORAGE_DIR / "exports" / "text"
LABELED_PDF_DIR = STORAGE_DIR / "exports" / "labeled-pdfs"

for _dir in [UPLOAD_DIR, EXPORT_JSON_DIR, EXPORT_TXT_DIR, LABELED_PDF_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

MODEL_REGISTRY = {
    "phobert": {
        "display_name": "PhoBERT",
        "kind": "transformer",
        "path": MODEL_ROOT / "phobert-drug-ner" / "model-best",
    },
    "xlmr": {
        "display_name": "XLM-RoBERTa",
        "kind": "transformer",
        "path": MODEL_ROOT / "xlmr-drug-ner" / "model-best",
    },
    "spacy": {
        "display_name": "spaCy",
        "kind": "spacy",
        "path": MODEL_ROOT / "spacy-drug-ner" / "model-best",
    },
}

DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "phobert")

_pipelines: Dict[str, object] = {}


ENTITY_ORDER = [
    "PERSON", "CHARGE", "LEGAL_ARTICLE", "SENTENCE",
    "DRUG", "DRUG_WEIGHT", "CRIME_TIME", "CRIME_LOC",
]

ENTITY_VI_LABELS = {
    "PERSON": "Tên bị cáo",
    "CHARGE": "Tội danh",
    "LEGAL_ARTICLE": "Điều luật",
    "SENTENCE": "Hình phạt",
    "DRUG": "Loại ma túy",
    "DRUG_WEIGHT": "Khối lượng ma túy",
    "CRIME_TIME": "Thời gian phạm tội",
    "CRIME_LOC": "Địa điểm phạm tội",
}

SECTION_VI_LABELS = {
    "noi_dung": "NỘI DUNG VỤ ÁN",
    "nhan_dinh": "NHẬN ĐỊNH CỦA TÒA ÁN",
    "quyet_dinh": "QUYẾT ĐỊNH",
    "unknown": "KHÔNG RÕ",
}


def safe_filename(name: str, default: str = "file") -> str:
    raw_stem = Path(name or default).stem
    slug = unicodedata.normalize("NFKD", raw_stem)
    slug = slug.encode("ascii", "ignore").decode("ascii") or default
    slug = re.sub(r"[^0-9A-Za-z._ -]+", "_", slug)
    slug = re.sub(r"[\s_]+", "_", slug).strip("._-").lower()
    return slug[:90] or default


def build_summary_lines(result: dict) -> list[str]:
    lines = []
    entities = result.get("entities") or {}
    for label in ENTITY_ORDER:
        values = []
        seen = set()
        for item in entities.get(label, []) or []:
            word = str(item.get("word") or item.get("text") or "").strip()
            key = word.lower()
            if word and key not in seen:
                seen.add(key)
                values.append(word)
        title = ENTITY_VI_LABELS.get(label, label)
        if values:
            lines.append(f"{title}: " + "; ".join(values))
        else:
            lines.append(f"{title}: Không tìm thấy")
    return lines


def write_json_export(result: dict, path: Path) -> None:
    export_data = dict(result)
    export_data.pop("model_dir", None)
    export_data.pop("model_root", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_txt_export(result: dict, path: Path) -> None:
    lines = [
        "KẾT QUẢ NHẬN DIỆN THỰC THỂ BẢN ÁN HÌNH SỰ MA TÚY",
        "=" * 70,
        f"Tên file: {result.get('filename', '')}",
        f"Model: {result.get('model_display_name') or result.get('model_name') or ''}",
        f"Thời gian xử lý: {result.get('elapsed_ms', '')} ms",
        "",
        "I. TÓM TẮT THỰC THỂ",
        "-" * 70,
        *build_summary_lines(result),
        "",
        "II. VĂN BẢN ĐƯỢC GÁN NHÃN",
        "-" * 70,
    ]
    for item in result.get("highlighted", []) or []:
        section = SECTION_VI_LABELS.get(item.get("section"), item.get("section", ""))
        lines.append(f"\n[{section}]")
        text = str(item.get("text") or "").strip()
        spans = sorted(item.get("spans") or [], key=lambda x: (int(x.get("start", 0)), int(x.get("end", 0))))
        if spans:
            tags = []
            for sp in spans:
                label = sp.get("entity") or sp.get("label")
                word = sp.get("word") or text[int(sp.get("start", 0)):int(sp.get("end", 0))]
                tags.append(f"[{label}: {word}]")
            lines.append("Thực thể: " + "; ".join(tags))
        lines.append(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _find_vietnamese_font() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for item in candidates:
        if item.exists():
            return str(item)
    return None


def write_labeled_pdf_export(original_pdf_path: Path, result: dict, path: Path) -> dict:
    try:
        import fitz
    except Exception as e:
        raise RuntimeError("Chưa cài PyMuPDF. Chạy: pip install pymupdf") from e

    original_pdf_path = Path(original_pdf_path)
    if not original_pdf_path.exists():
        raise RuntimeError(f"Không tìm thấy PDF gốc để highlight: {original_pdf_path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    label_colors = {
        "PERSON": (0.90, 0.12, 0.12),
        "DRUG": (0.42, 0.05, 0.68),
        "CRIME_TIME": (0.12, 0.53, 0.90),
        "CRIME_LOC": (0.26, 0.63, 0.28),
        "DRUG_WEIGHT": (1.00, 0.44, 0.00),
        "CHARGE": (0.00, 0.51, 0.56),
        "SENTENCE": (1.00, 0.92, 0.23),
        "LEGAL_ARTICLE": (0.99, 0.08, 0.78),
    }

    def clean_value(value: str) -> str:
        value = str(value or "")
        value = value.replace("\u00a0", " ")
        value = re.sub(r"\s+", " ", value).strip(" \t\n\r.,;:()[]{}\"“”‘’")
        return value

    def norm_token(value: str) -> str:
        value = clean_value(value).casefold()
        value = re.sub(r"[^0-9a-zà-ỹđ]+", "", value, flags=re.IGNORECASE)
        return value

    def collect_entities() -> list[dict]:
        items = []

        for item in result.get("entities_ordered") or []:
            label = item.get("label") or item.get("entity")
            text_value = clean_value(item.get("text") or item.get("word"))
            if label in label_colors and text_value:
                items.append({
                    "label": label,
                    "text": text_value,
                    "score": float(item.get("score", 1.0) or 1.0),
                })

        if not items:
            for label, values in (result.get("entities") or {}).items():
                for item in values or []:
                    text_value = clean_value(item.get("text") or item.get("word"))
                    if label in label_colors and text_value:
                        items.append({
                            "label": label,
                            "text": text_value,
                            "score": float(item.get("score", 1.0) or 1.0),
                        })

        seen = set()
        deduped = []
        for item in sorted(items, key=lambda x: len(x["text"]), reverse=True):
            key = (item["label"], item["text"].casefold())
            if key in seen:
                continue
            seen.add(key)
            if len(item["text"]) >= 2:
                deduped.append(item)
        return deduped

    def word_rect_search(page, query: str, max_hits: int = 25):
        q_tokens = [norm_token(x) for x in query.split() if norm_token(x)]
        if not q_tokens:
            return []

        words = page.get_text("words") or []
        page_tokens = []
        for w in words:
            token = norm_token(w[4])
            if token:
                page_tokens.append((token, fitz.Rect(w[0], w[1], w[2], w[3])))

        hits = []
        n = len(q_tokens)
        if n == 0 or len(page_tokens) < n:
            return hits

        for i in range(0, len(page_tokens) - n + 1):
            if [x[0] for x in page_tokens[i:i + n]] == q_tokens:
                rects = [x[1] for x in page_tokens[i:i + n]]
                hits.append(rects)
                if len(hits) >= max_hits:
                    break
        return hits

    def add_highlight(page, rects_or_quads, label: str, text_value: str) -> bool:
        color = label_colors.get(label, (1, 1, 0))
        try:
            annot = page.add_highlight_annot(rects_or_quads)
            annot.set_colors(stroke=color)
            annot.set_info(
                title=ENTITY_VI_LABELS.get(label, label),
                content=f"{ENTITY_VI_LABELS.get(label, label)}: {text_value}",
            )
            try:
                annot.update(opacity=0.35)
            except TypeError:
                annot.update()
            return True
        except Exception:
            return False

    doc = fitz.open(str(original_pdf_path))
    entities_to_highlight = collect_entities()

    stats = {
        "mode": "original_pdf_direct_highlight",
        "total_entities_to_search": len(entities_to_highlight),
        "matched_entities": 0,
        "matched_occurrences": 0,
        "unmatched": [],
    }

    for item in entities_to_highlight:
        label = item["label"]
        query = item["text"]
        matched_this_entity = 0

        if len(query) > 220:
            stats["unmatched"].append(item)
            continue

        for page in doc:
            try:
                quads = page.search_for(query, quads=True)
            except Exception:
                quads = []

            if quads:
                for quad in quads[:20]:
                    if add_highlight(page, [quad], label, query):
                        matched_this_entity += 1
                continue

            for rects in word_rect_search(page, query, max_hits=20):
                if add_highlight(page, rects, label, query):
                    matched_this_entity += 1

        if matched_this_entity > 0:
            stats["matched_entities"] += 1
            stats["matched_occurrences"] += matched_this_entity
        else:
            stats["unmatched"].append(item)

    stats["unmatched"] = [
        {"label": x["label"], "text": x["text"]}
        for x in stats["unmatched"][:80]
    ]

    if path.exists():
        path.unlink()
    doc.save(str(path), garbage=4, deflate=True)
    doc.close()

    return stats

def cleanup_old_files(max_age_seconds: int = 3600) -> None:
    now = time.time()
    for folder in [UPLOAD_DIR, EXPORT_JSON_DIR, EXPORT_TXT_DIR, LABELED_PDF_DIR]:
        for file_path in folder.glob("*"):
            if file_path.name == ".gitkeep" or not file_path.is_file():
                continue
            try:
                if now - file_path.stat().st_mtime > max_age_seconds:
                    file_path.unlink()
            except Exception:
                pass


def has_model_weight(p: Path, kind: str = "transformer") -> bool:
    if kind == "spacy":
        return (p / "config.cfg").exists() or (p / "meta.json").exists()

    return (
        (p / "model.safetensors").exists()
        or (p / "pytorch_model.bin").exists()
        or (p / "tf_model.h5").exists()
    )


def is_valid_model(model_name: str) -> bool:
    item = MODEL_REGISTRY.get(model_name)

    if not item:
        return False

    p = item["path"]
    kind = item["kind"]

    if kind == "spacy":
        return p.exists() and p.is_dir()

    return p.exists() and (p / "config.json").exists()


def get_model_dirs() -> list[dict]:
    models = []

    for name, item in MODEL_REGISTRY.items():
        path = item["path"]
        kind = item["kind"]

        models.append({
            "name": name,
            "display_name": item["display_name"],
            "kind": kind,
            "path": str(path),
            "exists": path.exists(),
            "has_weight": has_model_weight(path, kind),
            "is_valid": is_valid_model(name),
            "is_loaded": name in _pipelines,
            "is_default": name == DEFAULT_MODEL_NAME,
        })

    return models


def resolve_model_dir(model_name: Optional[str]) -> tuple[str, Path, str, str]:
    selected_name = model_name or DEFAULT_MODEL_NAME

    if selected_name not in MODEL_REGISTRY:
        available = ", ".join(MODEL_REGISTRY.keys())
        raise RuntimeError(
            f"Không tìm thấy model: {selected_name}. "
            f"Model hiện có: {available}"
        )

    item = MODEL_REGISTRY[selected_name]
    model_dir = item["path"]

    if not model_dir.exists():
        raise RuntimeError(
            f"Không tìm thấy thư mục model: {model_dir}"
        )

    if item["kind"] == "transformer" and not (model_dir / "config.json").exists():
        raise RuntimeError(
            f"Model transformer thiếu config.json: {model_dir}"
        )

    return selected_name, model_dir, item["display_name"], item["kind"]

def get_pipeline(model_name: Optional[str] = None):
    model_key, model_dir, display_name, kind = resolve_model_dir(model_name)

    if model_key not in _pipelines:
        from ner_pipeline import NERPipeline

        print("=" * 80)
        print("FASTAPI LOAD MODEL")
        print(f"MODEL_ROOT = {MODEL_ROOT}")
        print(f"MODEL_KEY  = {model_key}")
        print(f"MODEL_NAME = {display_name}")
        print(f"MODEL_KIND = {kind}")
        print(f"MODEL_DIR  = {model_dir}")
        print("=" * 80)

        _pipelines[model_key] = NERPipeline(
            model_dir=model_dir,
            model_name=model_key,
            model_display_name=display_name,
            model_kind=kind,
        )

    return _pipelines[model_key]


app = FastAPI(
    title="Drug NER API",
    description="Trích xuất thực thể từ bản án hình sự ma túy tiếng Việt bằng PhoBERT",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/exports/labeled-pdfs", StaticFiles(directory=str(LABELED_PDF_DIR)), name="labeled_pdfs")
app.mount("/exports/json", StaticFiles(directory=str(EXPORT_JSON_DIR)), name="export_json")
app.mount("/exports/text", StaticFiles(directory=str(EXPORT_TXT_DIR)), name="export_text")


# 2. FIX API ROUTE: Trả lại trang chủ "/" cho giao diện React
@app.get("/api")
def root():
    return {
        "status": "ok",
        "version": "2.0.0",
        "model_root": str(MODEL_ROOT),
        "loaded_models": list(_pipelines.keys()),
        "models_endpoint": "/models",
        "docs": "/docs",
        "note": "API trả JSON NER và hỗ trợ tải JSON/TXT/PDF đã gán nhãn.",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_root": str(MODEL_ROOT),
        "loaded_models": list(_pipelines.keys()),
    }


@app.get("/models")
def list_models():
    models = get_model_dirs()
    default_model = (
        next((m["name"] for m in models if m["is_valid"]), None)
        or (models[0]["name"] if models else None)
    )
    return {
        "model_root": str(MODEL_ROOT),
        "models": models,
        "default_model": default_model,
    }


@app.get("/model-info")
def model_info(model_name: Optional[str] = None):
    try:
        model_key, model_dir, display_name, kind = resolve_model_dir(model_name)

        return {
            "model_root": str(MODEL_ROOT),
            "model_name": model_key,
            "model_display_name": display_name,
            "model_kind": kind,
            "model_dir": str(model_dir),
            "exists": model_dir.exists(),
            "loaded": model_key in _pipelines,
            "files": sorted([p.name for p in model_dir.iterdir()]) if model_dir.exists() else [],
        }
    except Exception as e:
        raise HTTPException(404, str(e))


@app.post("/warmup")
def warmup(model_name: Optional[str] = Form(default=None)):
    try:
        pipe = get_pipeline(model_name)

        return {
            "status": "model loaded",
            "model_name": pipe.model_name,
            "model_display_name": pipe.model_display_name,
            "model_kind": pipe.model_kind,
            "model_dir": str(pipe.model_dir),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/download/json/{filename}")
def download_json(filename: str):
    path = EXPORT_JSON_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(404, "Không tìm thấy file JSON kết quả")
    return FileResponse(path, media_type="application/json", filename=path.name)


@app.get("/download/txt/{filename}")
def download_txt(filename: str):
    path = EXPORT_TXT_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(404, "Không tìm thấy file TXT kết quả")
    return FileResponse(path, media_type="text/plain; charset=utf-8", filename=path.name)


@app.get("/download/pdf/{filename}")
def download_labeled_pdf(filename: str):
    path = LABELED_PDF_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(404, "Không tìm thấy file PDF đã gán nhãn")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(default=None),
    content_mode: str = Form(default="raw"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chỉ hỗ trợ file PDF")
    if content_mode not in {"raw", "filtered"}:
        raise HTTPException(400, "content_mode chỉ nhận 'raw' hoặc 'filtered'")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "File quá lớn, tối đa 50MB")

    t0 = time.perf_counter()
    try:
        cleanup_old_files(max_age_seconds=int(os.environ.get("TEMP_FILE_TTL_SECONDS", "3600")))

        analysis_id = uuid.uuid4().hex[:12]
        safe_stem = safe_filename(file.filename, default="ban_an")
        uploaded_pdf_name = f"{analysis_id}_{safe_stem}.pdf"
        uploaded_pdf_path = UPLOAD_DIR / uploaded_pdf_name
        uploaded_pdf_path.write_bytes(content)

        pipe = get_pipeline(model_name)
        result = pipe.run(
            pdf_bytes=content,
            filename=file.filename,
            content_mode=content_mode,
        )
        result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        result["analysis_id"] = analysis_id
        result["model_name"] = pipe.model_name
        result["model_display_name"] = pipe.model_display_name
        result["model_kind"] = pipe.model_kind
        result["model_key"] = pipe.model_name
        result["model_dir"] = str(pipe.model_dir)
        result["model_root"] = str(MODEL_ROOT)

        json_name = f"{analysis_id}_{safe_stem}_ner.json"
        txt_name = f"{analysis_id}_{safe_stem}_ner.txt"
        pdf_name = f"{analysis_id}_{safe_stem}_labeled.pdf"

        json_path = EXPORT_JSON_DIR / json_name
        txt_path = EXPORT_TXT_DIR / txt_name
        pdf_path = LABELED_PDF_DIR / pdf_name

        result["files"] = {
            "uploaded_pdf_name": uploaded_pdf_name,
            "json_url": f"/download/json/{json_name}",
            "txt_url": f"/download/txt/{txt_name}",
            "labeled_pdf_url": f"/download/pdf/{pdf_name}",
            "view_labeled_pdf_url": f"/exports/labeled-pdfs/{pdf_name}",
        }
        result["json_download_url"] = result["files"]["json_url"]
        result["txt_download_url"] = result["files"]["txt_url"]
        result["labeled_pdf_url"] = result["files"]["labeled_pdf_url"]
        result["view_labeled_pdf_url"] = result["files"]["view_labeled_pdf_url"]
        result["highlighted_pdf_url"] = result["files"]["view_labeled_pdf_url"]

        write_txt_export(result, txt_path)
        result["pdf_highlight_stats"] = write_labeled_pdf_export(uploaded_pdf_path, result, pdf_path)
        write_json_export(result, json_path)

        return JSONResponse(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Lỗi xử lý: {e}")


# 3. FIX ĐƯỜNG DẪN UI: Trỏ đúng ra ngoài thư mục `backend` rồi mới vào `frontend`
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")