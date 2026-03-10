FROM python:3.12-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.10.4

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY chainlit.md ./

# Install locked runtime dependencies before copying source for better layer reuse.
RUN uv sync --locked --no-dev --no-install-project

# Expose port
EXPOSE 8000

# Copy Chainlit config and public assets
COPY .chainlit/ ./.chainlit/
COPY public ./public
COPY src ./src

# Run the same ASGI app used by the host-side local launcher.
CMD ["sh", "-c", ".venv/bin/python -m uvicorn src.app:chainlit_server_app --host 0.0.0.0 --port ${PORT:-8000}"]
