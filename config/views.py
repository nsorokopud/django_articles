from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import View


class BasicErrorView(View):
    error_code = -1
    error_message = ""
    template = "error.html"

    def dispatch(self, *args, **kwargs):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"HTTP Error {self.error_code}: {self.error_message}",
                }
            )
        context = {"error_code": self.error_code, "error_message": self.error_message}
        return render(self.request, self.template, context, status=self.error_code)


class Error403View(BasicErrorView):
    error_code = 403
    error_message = "Access forbidden"


class Error404View(BasicErrorView):
    error_code = 404
    error_message = "Page not found"


class Error405View(BasicErrorView):
    error_code = 405
    error_message = "Method not allowed"


class Error500View(BasicErrorView):
    error_code = 500
    error_message = "Internal server error"
