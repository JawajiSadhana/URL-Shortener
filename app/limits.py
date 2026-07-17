try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
except Exception:
    # Provide a no-op fallback for environments without slowapi installed
    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def _decorator(f):
                return f
            return _decorator

    limiter = _NoopLimiter()

__all__ = ("limiter",)
