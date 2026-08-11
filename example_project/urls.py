from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView


def privacy(request):
    return HttpResponse(
        "<h1>Privacy policy</h1>"
        "<p>Example privacy page for the script-consent demo.</p>"
        '<p><a href="/">Home</a> · <a href="/themed/">Themed banner</a></p>'
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("script-consent/", include("script_consent.urls")),
    path("privacy/", privacy, name="privacy"),
    path(
        "themed/",
        TemplateView.as_view(template_name="themed_banner.html"),
        name="themed_banner",
    ),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]
