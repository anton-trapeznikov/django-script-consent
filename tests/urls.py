from django.contrib import admin
from django.http import HttpResponse
from django.template import engines
from django.urls import include, path


def home(request):
    tpl = engines["django"].from_string("""
        {% load script_consent %}
        <!DOCTYPE html>
        <html><head>{% consent_scripts "head" %}</head>
        <body>
        {% csrf_token %}
        {% consent_scripts "body_start" %}
        <h1>Home</h1>
        {% consent_banner %}
        {% consent_scripts "body_end" %}
        </body></html>
        """)
    return HttpResponse(tpl.render({}, request))


urlpatterns = [
    path("admin/", admin.site.urls),
    path("script-consent/", include("script_consent.urls")),
    path("", home, name="home"),
]
