from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('', views.contacts_home, name='list'),
    path('tags/', views.tags_manager, name='tags_manager'),
    path('tags/bulk-update/', views.bulk_update_contact_tags, name='bulk_update_contact_tags'),
    path('import-csv/', views.import_csv, name='import_csv'),
    path('add/', views.add_contact, name='add_contact'),
    path('delete/<int:contact_id>/', views.delete_contact, name='delete_contact'),
    path('delete-list/<int:list_id>/', views.delete_list, name='delete_list'),
]