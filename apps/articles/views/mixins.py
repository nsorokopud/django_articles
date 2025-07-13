from django.http import Http404


class AllowOnlyAuthorMixin:
    def dispatch(self, *args, **kwargs):
        if self.get_object().author != self.request.user:
            raise Http404
        return super().dispatch(*args, **kwargs)
