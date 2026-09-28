from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_VALUE_ERROR_PREFIX = "Value error, "


def _message(error: dict) -> str:
    field = ".".join(str(p) for p in error["loc"] if p not in ("body", "query", "path"))
    msg: str = error["msg"]
    # 我们自己的校验器抛出的 ValueError 已经是中文提示，直接使用
    if msg.startswith(_VALUE_ERROR_PREFIX):
        return msg.removeprefix(_VALUE_ERROR_PREFIX)
    if error["type"] == "missing":
        return f"缺少必填项：{field}" if field else "缺少请求内容"
    return f"参数有误：{field}" if field else "请求格式有误"


def register_error_handlers(app: FastAPI) -> None:
    """所有错误响应统一为 {"detail": "中文提示"}，前端可直接显示。"""

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"detail": _message(exc.errors()[0])},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
