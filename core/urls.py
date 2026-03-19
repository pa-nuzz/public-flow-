from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_view, name='home'),
    path('contacts/', include('apps.contacts.urls', namespace='contacts')),
    path('campaign/', include('apps.campaigns.urls', namespace='campaigns')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('intelligence/', include('apps.intelligence.urls', namespace='intelligence')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


