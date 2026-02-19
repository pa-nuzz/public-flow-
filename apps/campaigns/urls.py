from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.campaign_create, name='campaign_create'),
]