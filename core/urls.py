from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view
from apps.accounts.views import settings_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_view, name='home'),
    path('campaign/', include('apps.campaigns.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('intelligence/', include('apps.intelligence.urls')),
    path('settings/', settings_view, name='settings'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)