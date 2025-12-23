from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import tiktoken
from fastapi import FastAPI
from pydantic import BaseModel

from src.config import Settings
from src.storage import StoredChunk, VectorStore


@dataclass(slots=True)
class RetrievedContext:
    chunks: list[StoredChunk]
    prompt: str


class ChatRequest(BaseModel):
    query: str
    history: list[tuple[str, str]] | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


def build_prompt(query: str, chunks: Iterable[StoredChunk], max_tokens: int = 1500) -> str:
    encoder = tiktoken.get_encoding("cl100k_base")
    context_parts: list[str] = []
    token_budget = max_tokens

    for chunk in chunks:
        snippet = f"Source: {chunk.url}\nContent: {chunk.text}\n---"
        tokens = len(encoder.encode(snippet))
        if tokens > token_budget:
            break
        context_parts.append(snippet)
        token_budget -= tokens

    context_block = "\n\n".join(context_parts)
    instructions = (
        "You are an assistant that answers strictly from the provided context. "
        "If the answer is not present, reply with 'I do not have that information yet.'"
    )
    return f"{instructions}\n\nContext:\n{context_block}\n\nQuestion: {query}\nAnswer:"


def create_chat_service(settings: Settings) -> FastAPI:
    vector_store = VectorStore(settings)
    app = FastAPI(title="Website Knowledge Chatbot")

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        hits = vector_store.search(request.query)
        prompt = build_prompt(request.query, hits)
        # Note: Delegate to upstream LLM such as OpenAI, Azure OpenAI, or local model.
        # The LLM call is abstracted here to keep credentials/configuration outside of this codebase.
        synthetic_answer = (
            "This is a placeholder answer. Plug in your LLM provider to respond using the prompt:\n"
            f"{prompt}"
        )
        sources = list({hit.url for hit in hits})
        return ChatResponse(answer=synthetic_answer, sources=sources)

    return app
