from __future__ import annotations

from fastapi import FastAPI

from src.config import settings_from_env
from src.rag import create_chat_service


settings = settings_from_env()
app: FastAPI = create_chat_service(settings)
