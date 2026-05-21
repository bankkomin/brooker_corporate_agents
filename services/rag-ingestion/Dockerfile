# services/rag-ingestion/Dockerfile
FROM python:3.11-slim

# System deps:
#   curl                       — healthcheck
#   antiword                   — legacy .doc reader (chunker._extract_doc)
#   libxml2 libxslt1.1 libmagic1 — runtime deps for python-pptx + extract-msg
#   tesseract-ocr + langs      — OCR fallback for scanned PDFs (chunker._extract_pdf)
#   poppler-utils ghostscript  — pdf2image / ocrmypdf rasterisation
#   tesseract-ocr-tha          — Thai language pack (Thai SEC corpus)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    antiword \
    libxml2 \
    libxslt1.1 \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-tha \
    poppler-utils \
    ghostscript \
    qpdf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 3004

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:3004/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3004"]
