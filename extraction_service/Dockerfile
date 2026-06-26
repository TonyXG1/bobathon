FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy service files
COPY pyproject.toml .
COPY *.py ./

# Copy contracts package (needed for imports)
COPY --from=contracts /app/contracts /app/contracts

# Install dependencies
RUN uv sync --no-dev

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8081/health', timeout=5.0)" || exit 1

# Run service
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
