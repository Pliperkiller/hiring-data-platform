FROM python:3.12-slim

WORKDIR /code

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.interface.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
