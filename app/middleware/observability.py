import time
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration seconds",
    ["method", "path"],
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        path = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            path=path,
            status_code=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(
            time.time() - start_time
        )
        return response
