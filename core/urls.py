from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_page, name='home'),
    path('campaign/', include('apps.campaigns.urls')),
    # path('dashboard/', include('apps.campaigns.urls')), # Later
    # path('accounts/', include('apps.accounts.urls')), # Later
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)