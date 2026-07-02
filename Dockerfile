FROM python:3.12-slim

WORKDIR /code

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY docker-entrypoint.sh ./

RUN pip install --no-cache-dir . && chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
