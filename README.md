# Drug NER — Nhận diện thực thể trong bản án hình sự ma túy tiếng Việt

Hệ thống nhận diện thực thể có tên (Named Entity Recognition) trên bản án hình sự về ma túy tiếng Việt, sử dụng mô hình **PhoBERT** fine-tune cho 8 loại thực thể. Hệ thống cho phép tải lên bản án PDF, tự động trích xuất văn bản, nhận diện và đánh dấu các thực thể, đồng thời xuất kết quả ra JSON/TXT/PDF.

🔗 **Demo trực tuyến:** https://baob2112-drug-ner.hf.space

---

## 1. Tính năng chính

- Tải lên bản án dạng **PDF**, tự động trích xuất và cắt đoạn theo từng phần (nội dung vụ án, nhận định, quyết định).
- Nhận diện **8 nhãn thực thể**:

  | Nhãn | Ý nghĩa |
  |------|---------|
  | `PERSON` | Tên bị cáo |
  | `CHARGE` | Tội danh |
  | `LEGAL_ARTICLE` | Điều luật |
  | `SENTENCE` | Hình phạt |
  | `DRUG` | Loại ma túy |
  | `DRUG_WEIGHT` | Khối lượng ma túy |
  | `CRIME_TIME` | Thời gian phạm tội |
  | `CRIME_LOC` | Địa điểm phạm tội |

- Hiển thị kết quả theo nhiều chế độ: highlight văn bản, xem PDF đã gán nhãn, tóm tắt và chi tiết thực thể.
- Xuất kết quả ra **JSON / TXT / PDF** đã gán nhãn.
- Hỗ trợ chọn nhiều mô hình (PhoBERT, XLM-RoBERTa, spaCy) phục vụ so sánh.

---

## 2. Công nghệ sử dụng

- **Backend:** Python, FastAPI, PyTorch, HuggingFace Transformers (PhoBERT), PyMuPDF.
- **Frontend:** React + Vite.
- **Triển khai:** Docker, Hugging Face Spaces.

---

## 3. Cấu trúc thư mục

```
NER-NLP-Project/
├── backend/
│   ├── api.py                        # FastAPI app (endpoint /analyze, /models, ...)
│   ├── run_api.py                    # Khởi chạy uvicorn
│   ├── ner_pipeline.py               # Pipeline xử lý PDF -> predict -> JSON
│   ├── ner_predictor.py              # Nạp model và dự đoán nhãn
│   ├── ner_dataset.py                # Dataset loader (BIO)
│   ├── ner_evaluator.py              # Đánh giá bằng seqeval
│   ├── train_ner_model.py            # Huấn luyện PhoBERT
│   ├── extract_prediction_snippets.py# Cắt đoạn PDF để predict
│   ├── extract_training_snippets.py  # Cắt đoạn PDF để gán nhãn (DOCX)
│   ├── convert_docx_to_doccano.py    # Chuyển DOCX -> JSONL (Doccano)
│   ├── merge_annotated_dataset.py    # Gộp dữ liệu đã gán nhãn
│   ├── requirements.txt
│   └── models/                       # (không đẩy lên GitHub — xem mục 6)
│       └── phobert-drug-ner/model-best/
└── frontend/
    ├── src/
    │   ├── pages/                     # HomePage, AnalyzePage, HistoryPage, ...
    │   ├── components/                # NERResult, HighlightedText, PdfViewer, ...
    │   └── config.js
    ├── package.json
    └── dist/                          # Bản build tĩnh (FastAPI serve)
```

---

## 4. Yêu cầu môi trường

- Python **3.10+**
- Node.js **18+**
- RAM tối thiểu **2 GB** (để nạp model PhoBERT)
- Thư mục model đã huấn luyện đặt tại `backend/models/phobert-drug-ner/model-best/`
  (gồm `config.json`, `model.safetensors` và các tệp tokenizer của PhoBERT)

---

## 5. Cài đặt và chạy trên máy cục bộ

### 5.1. Backend

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python run_api.py
```

Backend chạy tại `http://localhost:8000` (tài liệu API tại `http://localhost:8000/docs`).

### 5.2. Frontend

```bash
cd frontend
npm install
npm run build      # tạo thư mục dist/ để FastAPI serve
```

Sau khi build, truy cập `http://localhost:8000` để dùng giao diện web.

> Khi phát triển frontend riêng: chạy `npm run dev` (cổng 5173) và đặt biến `VITE_API_URL=http://localhost:8000` để gọi sang backend.

---

## 6. Mô hình

Các tệp model (`*.safetensors`) có dung lượng lớn (> 100 MB) nên **không được đưa lên GitHub** mà lưu trên Hugging Face. Trước khi chạy, hãy đặt model vào:

```
backend/models/phobert-drug-ner/model-best/
```

Nếu muốn lưu model trên GitHub, dùng **Git LFS**:

```bash
git lfs install
git lfs track "*.safetensors"
```

---

## 7. Triển khai trên Hugging Face Spaces

Hệ thống được đóng gói bằng Docker và triển khai trên Hugging Face Spaces (CPU, 16 GB RAM):

1. Tạo Space mới, chọn SDK **Docker**.
2. Đẩy mã nguồn kèm `Dockerfile`, `frontend/dist` và thư mục `models/` (dùng Git LFS cho model).
3. Hugging Face tự build và chạy dịch vụ ở cổng 7860.

Ứng dụng đang chạy tại: **https://baob2112-drug-ner.hf.space**

---

## 8. Các endpoint API chính

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/analyze` | Tải PDF lên và nhận kết quả NER (JSON) |
| `GET`  | `/models` | Danh sách model khả dụng |
| `GET`  | `/download/json/{file}` | Tải kết quả JSON |
| `GET`  | `/download/txt/{file}` | Tải kết quả TXT |
| `GET`  | `/download/pdf/{file}` | Tải PDF đã gán nhãn |
| `GET`  | `/docs` | Tài liệu API (Swagger UI) |

---

## 9. Quy trình huấn luyện (tóm tắt)

PDF bản án → trích & cắt đoạn → gán nhãn bằng Doccano → gộp thành tập dữ liệu JSONL → chia train/validation/test theo từng bản án → huấn luyện PhoBERT (Token Classification, 17 nhãn BIO, Weighted CrossEntropyLoss, Early Stopping) → đánh giá bằng seqeval.

---

## 10. Thông tin đồ án

- **Đề tài:** Xây dựng hệ thống nhận diện thực thể có tên trong bản án hình sự ma túy
- **Sinh viên thực hiện:** Đinh Quốc Bảo
- **Giảng viên hướng dẫn:** ThS. Trần Phong Nhã
- **Đơn vị:** Bộ môn Công nghệ Thông tin — Trường Đại học Giao thông Vận tải, Phân hiệu tại TP. Hồ Chí Minh
