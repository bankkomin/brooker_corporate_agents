FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn[standard]
COPY src/ ./src/
EXPOSE 3008
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3008"]
