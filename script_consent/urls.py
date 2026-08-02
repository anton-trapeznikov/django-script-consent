from django.urls import path

from script_consent import views

app_name = "script_consent"

urlpatterns = [
    path("accept/", views.accept_consent, name="accept"),
    path("dismiss/", views.dismiss_banner, name="dismiss"),
    path("withdraw/", views.withdraw_consent, name="withdraw"),
]
