import threading

_request_local = threading.local()


def get_request_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditRequestMiddleware:
    """Store request on thread-local for audit signal handlers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request_local.request = request
        try:
            return self.get_response(request)
        finally:
            _request_local.request = None


def get_current_request():
    return getattr(_request_local, "request", None)
