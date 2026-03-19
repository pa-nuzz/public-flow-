from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('', views.contact_list, name='list'),
    path('import-csv/', views.import_csv, name='import_csv'),
]