FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy pyproject.toml first for dependency caching
COPY pyproject.toml .

# Copy all Python files
COPY *.py ./
COPY tests/ ./tests/

# Copy dataset for taxonomy
COPY ../dataset/taxonomy.json /app/dataset/taxonomy.json

# Install dependencies
RUN uv pip install --system -e .

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8081/health', timeout=5.0)" || exit 1

# Run service
CMD ["uvicorn", "extraction_service.main:app", "--host", "0.0.0.0", "--port", "8081"]