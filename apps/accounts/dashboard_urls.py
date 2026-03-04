from django.urls import path
from .views import dashboard_view, settings_view

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("dashboard/settings/", settings_view, name="settings"),
]