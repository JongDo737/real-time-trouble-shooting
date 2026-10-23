"""OpenAI 호환 LLM 호출 공통 모듈 (번역 · RAG 평가 · 생성이 함께 사용)."""

from dataclasses import dataclass
from functools import lru_cache

import openai
from fastapi import Depends
from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.errors import ApiError


@dataclass
class ChatResult:
    content: str
    in_tok: int
    out_tok: int


@lru_cache
def _build_client(api_key: str, base_url: str, timeout: float) -> AsyncOpenAI:
    # 재시도는 백엔드가 담당하므로 SDK 자동 재시도는 끈다
    return AsyncOpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout, max_retries=0)


def get_llm_client(settings: Settings = Depends(get_settings)) -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise ApiError(503, "LLM_UNAVAILABLE", "LLM API 키가 설정되지 않았습니다.")
    return _build_client(settings.openai_api_key, settings.llm_base_url, settings.llm_timeout_seconds)


def require_model(model: str, env_name: str) -> str:
    if not model:
        raise ApiError(503, "LLM_UNAVAILABLE", f"{env_name}이(가) 설정되지 않았습니다.")
    return model


async def chat(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    *,
    json_mode: bool = False,
    timeout: float | None = None,
) -> ChatResult:
    """timeout을 주면 클라이언트 기본 제한 대신 이 호출에만 그 제한을 쓴다."""
    kwargs: dict = {"model": model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if timeout is not None:
        kwargs["timeout"] = timeout

    try:
        res = await client.chat.completions.create(**kwargs)
    except openai.APITimeoutError:
        raise ApiError(503, "LLM_TIMEOUT", "모델 응답 시간이 초과되었습니다.")
    except openai.OpenAIError:
        raise ApiError(503, "LLM_UNAVAILABLE", "모델 호출에 실패했습니다.")

    content = (res.choices[0].message.content or "") if res.choices else ""
    usage = res.usage
    return ChatResult(
        content=content,
        in_tok=getattr(usage, "prompt_tokens", 0) or 0,
        out_tok=getattr(usage, "completion_tokens", 0) or 0,
    )


async def embed(
    client: AsyncOpenAI, model: str, text: str, *, timeout: float | None = None
) -> list[float]:
    kwargs: dict = {"model": model, "input": text}
    if timeout is not None:
        kwargs["timeout"] = timeout
    try:
        res = await client.embeddings.create(**kwargs)
    except openai.APITimeoutError:
        raise ApiError(503, "LLM_TIMEOUT", "임베딩 응답 시간이 초과되었습니다.")
    except openai.OpenAIError:
        raise ApiError(503, "LLM_UNAVAILABLE", "임베딩 호출에 실패했습니다.")
    return list(res.data[0].embedding)
