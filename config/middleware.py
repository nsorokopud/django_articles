import logging


logger = logging.getLogger("uncatched_errors_logger")


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self._get_response = get_response

    def __call__(self, request):
        return self._get_response(request)

    def process_exception(self, request, exception):
        logger.error(exception, exc_info=True)
