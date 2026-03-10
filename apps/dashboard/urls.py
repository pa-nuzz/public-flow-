from django.urls import path
from .views import dashboard_view, settings_view

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("dashboard/settings/", settings_view, name="settings"),
    path("dashboard/addsender/", settings_view, name="add_sender"),

]