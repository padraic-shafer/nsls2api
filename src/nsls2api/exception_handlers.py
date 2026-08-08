from asgi_correlation_id import correlation_id
from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler

from nsls2api.main import app


# This is to make sure we add the request ID to the response headers for the case
# of unhandled server errors.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return await http_exception_handler(
        request,
        HTTPException(
            500,
            "Internal server error - unhandled exception",
            headers={"X-Request-ID": correlation_id.get() or ""},
        ),
    )
