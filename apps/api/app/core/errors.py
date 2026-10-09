from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, *, current_version=None, details=None):
        self.status, self.code, self.message = status, code, message
        self.current_version, self.details = current_version, details or {}

    def envelope(self, meta):
        return {"error": {"code": self.code, "message": self.message,
                          "retryable": self.code in ("COMMAND_IN_PROGRESS", "SERVICE_UNAVAILABLE"),
                          "current_version": self.current_version, "details": self.details}, "meta": meta}


def request_meta(request: Request):
    return {"request_id": request.state.request_id, "dataset_id": "shiftlink-demo", "demo_mode": True}


def error_response(request: Request, error: DomainError):
    return JSONResponse(error.envelope(request_meta(request)), status_code=error.status)


def install_error_handlers(app):
    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request, DomainError(422, "VALIDATION_ERROR", "입력 형식을 확인해 주세요.",
            details={"fields": [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]}))

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "RESOURCE_NOT_FOUND"}.get(exc.status_code, "HTTP_ERROR")
        return error_response(request, DomainError(exc.status_code, code, "요청을 처리할 수 없습니다."))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(request, DomainError(503, "SERVICE_UNAVAILABLE", "저장소에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."))
