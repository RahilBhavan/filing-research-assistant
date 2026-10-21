# Filing research server over the Strategy / BitMine / Coinbase corpus.
# Build:  docker build -t filing-research .
# Run:    docker run --rm -p 8765:8765 -e ANTHROPIC_API_KEY filing-research
# Without ANTHROPIC_API_KEY the cited-answer writer is the model-free extractive fallback.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/.models HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app
COPY setup.py setup.cfg pyproject.toml README.md ./
COPY filing_assistant ./filing_assistant
RUN pip install --no-cache-dir ".[embed,llm]"

# Bake the query encoder into the image so the container never downloads at request time.
RUN python -c "from filing_assistant.dense import FastEmbedEncoder; FastEmbedEncoder().encode(['warm up'])"

COPY corpora/treasury ./corpora/treasury
RUN useradd --create-home --uid 10001 app && chown -R app /app/.models
USER app

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/api/config', headers={'Host': '127.0.0.1:8765'}))"
# The server rejects unknown Host headers; set FILING_ALLOWED_HOSTS to the public hostname when deployed.
CMD ["python", "-m", "filing_assistant", "--corpus", "corpora/treasury", "serve", "--host", "0.0.0.0", "--port", "8765"]
