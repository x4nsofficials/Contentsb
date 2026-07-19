# Playwright's own image ships Chromium (and all its system deps) pre-installed at a
# version matched to the playwright pip package below -- avoids a slow/fragile
# `playwright install --with-deps` step at build time.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

COPY research/requirements.txt research/requirements.txt
RUN pip install --no-cache-dir -r research/requirements.txt

COPY research/ research/

WORKDIR /app/research
ENV PYTHONUNBUFFERED=1
EXPOSE 3456

CMD ["python3", "server.py"]
