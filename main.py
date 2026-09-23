from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import health
from app.api.v1 import auth
from app.api.v1 import workflow
from app.api.v1 import automation


setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)


app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(workflow.router, prefix=settings.API_V1_STR + "/workflow")
app.include_router(automation.router, prefix=settings.API_V1_STR + "/automation")


@app.get("/")
async def root():
    return {"message": "Welcome to Agentic GenAI Framework"}
