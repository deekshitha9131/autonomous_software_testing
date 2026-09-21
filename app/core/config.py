import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.


class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Agentic GenAI Framework")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")


settings = Settings()
