FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY scripts scripts
COPY domain domain
RUN adduser --system --uid 10001 analytics
USER analytics
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
