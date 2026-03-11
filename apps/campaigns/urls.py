from django.urls import path
from . import views



app_name = "campaigns"

urlpatterns = [
    path('create/', views.campaign_create, name='campaign_create'),
]