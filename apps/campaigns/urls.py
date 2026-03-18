from django.urls import path
from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("create/", views.campaign_create, name="campaign_create"),
    path("<int:campaign_id>/edit/", views.campaign_edit, name="campaign_edit"),
    path("<int:campaign_id>/send/", views.campaign_send, name="campaign_send"),
]