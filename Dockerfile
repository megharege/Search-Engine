# Base: python:3.10-slim for CPU-only deployment
FROM python:3.10-slim

WORKDIR /app

# system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# torch for CPU (required by sentence-transformers)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Python deps
COPY requirements.docker.txt ./
RUN pip install --no-cache-dir -r requirements.docker.txt

# source + generated data (normalized + embeddings must exist before docker build)
COPY src/            src/
COPY data/combined.jsonl    data/combined.jsonl
COPY data/embeddings.npz    data/embeddings.npz
COPY mcp_server.py   ./
COPY pipeline.py     ./
COPY app.py          ./
COPY .streamlit/     .streamlit/

# ports: 8000 = MCP/FastAPI, 8501 = Streamlit
EXPOSE 8000 8501

# default: run the MCP server
# docker-compose overrides CMD for the streamlit service
CMD ["uvicorn", "mcp_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
