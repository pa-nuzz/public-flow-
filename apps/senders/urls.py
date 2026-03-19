from django.urls import path

from .views import verify_sender

app_name = 'senders'

urlpatterns = [
    path('verify/', verify_sender, name='verify_sender'),
]
