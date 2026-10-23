from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """api2.md의 공통 오류 응답으로 변환되는 예외."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(
    request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        # 본문이 JSON이 아니면 loc이 글자 위치(숫자)뿐이라 필드 목록으로는 알아볼 수 없다
        broken = next((e for e in errors if e["type"] == "json_invalid"), None)
        if broken:
            position = broken["loc"][1] if len(broken["loc"]) > 1 else "?"
            return error_response(
                request,
                422,
                "VALIDATION_ERROR",
                f"요청 본문이 올바른 JSON이 아닙니다 ({position}번째 글자 근처). 쉼표나 따옴표를 확인하세요.",
            )
        # 입력값(통화 내용 등)은 응답에 되돌려 주지 않고 필드 위치만 알린다
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) or "body" for e in errors})
        # 우리가 모델에 직접 적은 검증 문구(value_error)에는 입력값이 들어 있지 않으므로 함께 알려 준다
        rules = [e["msg"].removeprefix("Value error, ") for e in errors if e["type"] == "value_error"]
        message = f"요청 필드 검증 실패: {', '.join(fields)}"
        if rules:
            message += f" — {' '.join(rules)}"
        return error_response(request, 422, "VALIDATION_ERROR", message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return error_response(request, 500, "INTERNAL_ERROR", "서버 내부 오류")
