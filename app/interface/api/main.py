from fastapi import FastAPI

app = FastAPI(title="Hiring Data Platform API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
