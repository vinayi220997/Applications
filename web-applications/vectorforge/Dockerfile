FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    VF_DATA_DIR=/data/jobs
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vectorforge ./vectorforge
RUN useradd --create-home --uid 10001 vf && mkdir -p /data/jobs && chown -R vf /data
USER vf
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["uvicorn", "vectorforge.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
