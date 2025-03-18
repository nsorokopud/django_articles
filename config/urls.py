from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config import views as project_views


urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("select2/", include("django_select2.urls")),
    path("", include("articles.urls")),
    path("", include("users.urls")),
    path("", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("admin/", admin.site.urls))
    urlpatterns.append(
        path("__debug__/", include("debug_toolbar.urls")),
    )
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns.append(path("__djangoblog__/", admin.site.urls))

# Error handlers
handler400 = project_views.Error400View.as_view()
handler403 = project_views.Error403View.as_view()
handler404 = project_views.Error404View.as_view()
handler500 = project_views.Error500View.as_view()
