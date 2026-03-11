from django.urls import path
from .views import analyze_spam

app_name = "intelligence"

urlpatterns = [
    path('api/analyze/', analyze_spam, name='analyze_spam'),
]
