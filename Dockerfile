FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=example_project.settings \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md MANIFEST.in LICENSE ./
COPY script_consent ./script_consent
RUN pip install --no-cache-dir -e .

COPY example_project ./example_project
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /data

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "example_project/manage.py", "runserver", "0.0.0.0:8000"]
