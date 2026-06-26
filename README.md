---
title: Drug NER PhoBERT
emoji: ⚖️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Drug NER PhoBERT

Hệ thống nhận diện thực thể (NER) trong bản án hình sự ma túy tiếng Việt.
Backend FastAPI + model PhoBERT, frontend React.

- Upload PDF bản án → trích đoạn → PhoBERT predict 8 nhãn → highlight + xuất JSON/TXT/PDF.
- 8 nhãn: PERSON, DRUG, DRUG_WEIGHT, CRIME_TIME, CRIME_LOC, CHARGE, SENTENCE, LEGAL_ARTICLE.

Mở app: nhấn vào tab **App** phía trên bên phải của Space này.

> Khối `---` ở đầu file là cấu hình bắt buộc của Hugging Face Spaces. **Không xóa.**
> `sdk: docker` và `app_port: 7860` phải khớp với Dockerfile.
