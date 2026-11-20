FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt && \
    useradd --system --uid 10001 --create-home explorer && \
    mkdir -p /data /vectors && chown explorer /data /vectors
COPY backend ./backend
USER explorer
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
