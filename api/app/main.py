from fastapi import FastAPI

app = FastAPI(title="Woodshed API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used by Docker, CI and the hosting platform."""
    return {"status": "ok"}
