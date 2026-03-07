FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock README.md ./
COPY chainlit.md ./
# Copy Chainlit config and public assets
COPY .chainlit/ ./.chainlit/
COPY public ./public
COPY src ./src

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Expose port
EXPOSE 8000

# Run Chainlit app (Azure can inject PORT)
CMD ["sh", "-c", "chainlit run src/app.py --host 0.0.0.0 --port ${PORT:-8000}"]
