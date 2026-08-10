from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.admin.auth import AdminDisabledError
from app.core.error_codes import AppException, CommonErrorCodes, error_response
from app.core.trace import current_trace_id


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                {**error_response(CommonErrorCodes.INVALID_PARAMS, {"detail": exc.errors()}), "traceId": current_trace_id()}
            ),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        response = exc.to_response()
        response["traceId"] = current_trace_id()
        return JSONResponse(status_code=200, content=jsonable_encoder(response))

    @app.exception_handler(AdminDisabledError)
    async def admin_disabled_exception_handler(request: Request, exc: AdminDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=jsonable_encoder(
                {
                    "errCode": "503001",
                    "errMsg": str(exc),
                    "data": {},
                    "traceId": current_trace_id(),
                }
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code_map = {
            401: CommonErrorCodes.UNAUTHORIZED,
            403: CommonErrorCodes.FORBIDDEN,
            404: CommonErrorCodes.NOT_FOUND,
            409: CommonErrorCodes.CONFLICT,
        }
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                {
                    **error_response(
                        code_map.get(exc.status_code, CommonErrorCodes.INTERNAL_ERROR),
                        {},
                        message=exc.detail if isinstance(exc.detail, str) else "请求处理失败",
                    ),
                    "traceId": current_trace_id(),
                }
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({**error_response(CommonErrorCodes.INTERNAL_ERROR, {}), "traceId": current_trace_id()}),
        )
