from django.urls import path
from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("create/", views.campaign_create, name="campaign_create"),
    path("<int:campaign_id>/analytics/", views.campaign_analytics, name="campaign_analytics"),
    path("<int:campaign_id>/analytics/export/", views.campaign_analytics_export_csv, name="campaign_analytics_export_csv"),
    path("<int:campaign_id>/view/", views.campaign_view, name="campaign_view"),
    path("<int:campaign_id>/edit/", views.campaign_edit, name="campaign_edit"),
    path("<int:campaign_id>/duplicate/", views.campaign_duplicate, name="campaign_duplicate"),
    path("<int:campaign_id>/send/", views.campaign_send, name="campaign_send"),
    path("<int:campaign_id>/retry-failed/", views.campaign_retry_failed, name="campaign_retry_failed"),
    path("<int:campaign_id>/delete/", views.campaign_delete, name="campaign_delete"),
    path("track/open/<str:token>/", views.campaign_track_open, name="track_open"),
    path("track/click/<str:token>/", views.campaign_track_click, name="track_click"),
    # Email Templates
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
    path("templates/<int:template_id>/edit/", views.template_edit, name="template_edit"),
    path("templates/<int:template_id>/delete/", views.template_delete, name="template_delete"),
    path("templates/<int:template_id>/use/", views.template_use, name="template_use"),
]