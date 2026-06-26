# ============================================================
# Drug NER PhoBERT - Hugging Face Spaces (Docker SDK)
# Backend FastAPI + Frontend React (build san trong frontend/dist)
# Lang nghe cong 7860 (cong mac dinh cua HF Spaces)
# ============================================================
FROM python:3.10-slim

# --- System deps: build PyMuPDF + font tieng Viet cho PDF highlight ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# --- HF Spaces khuyen dung user UID 1000 (khong chay root) ---
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    MODEL_NAME=phobert \
    HF_HOME=/home/user/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# --- Cai torch CPU-only TRUOC (nhe hon nhieu, khong keo CUDA ~2GB) ---
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# --- Copy toan bo source: code .py + models/ + frontend/dist ---
COPY --chown=user:user . .

# 👉 THÊM DÒNG NÀY: Di chuyển vào thư mục backend chứa file api.py
WORKDIR /home/user/app/backend

EXPOSE 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
