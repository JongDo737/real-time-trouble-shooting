import time

from fastapi import APIRouter, Depends
from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.schemas import ErrorResponse, TranslateRequest, TranslateResponse, Usage
from app.services.glossary import get_glossary
from app.services.llm import get_llm_client, require_model
from app.services.translate import translate_text

router = APIRouter(tags=["통번역"])


@router.post(
    "/translate",
    response_model=TranslateResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="발화 1건 통번역",
)
async def translate(
    req: TranslateRequest,
    settings: Settings = Depends(get_settings),
    client: AsyncOpenAI = Depends(get_llm_client),
):
    model = require_model(settings.translate_model, "TRANSLATE_MODEL")
    started = time.perf_counter()
    # 서버 용어집 파일에서, 이 문장에 나온 용어만 프롬프트에 넣는다
    glossary = get_glossary(settings.glossary_path).select(req.text, req.source_lang, req.target_lang)

    result = await translate_text(
        client,
        model,
        text=req.text,
        target_lang=req.target_lang,
        source_lang=req.source_lang,
        speaker=req.speaker,
        equipment_name=req.equipment_name,
        error_code=req.error_code,
        context=[c.model_dump() for c in req.context] if req.context else None,
        glossary=glossary or None,
    )

    return TranslateResponse(
        session_id=req.session_id,
        utterance_id=req.utterance_id,
        translated_text=result.translated_text,
        source_lang=result.source_lang,
        target_lang=req.target_lang,
        latency_ms=round((time.perf_counter() - started) * 1000),
        usage=Usage(in_tok=result.in_tok, out_tok=result.out_tok),
    )
