from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("profile/", views.profile_view, name="profile"),
]