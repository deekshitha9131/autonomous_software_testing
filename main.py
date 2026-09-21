from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import health


setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)


app.include_router(health.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Welcome to Agentic GenAI Framework"}
