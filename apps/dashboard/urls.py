from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("templates/", views.templates_view, name="templates"),
    path("settings/", views.settings_view, name="settings"),
    path("profile/", views.profile_view, name="profile"),
    path("notifications/clear/", views.clear_notifications_view, name="clear_notifications"),
    
]