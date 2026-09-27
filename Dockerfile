FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port (default 7860 for Hugging Face Spaces or 5000 for standard)
EXPOSE 7860

# Run with Gunicorn using gthread worker for SSE streaming support
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "8", "--timeout", "180", "--bind", "0.0.0.0:7860", "app:app"]
