from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Landing
    path('', landing_view, name="landing"),

    # Accounts
    path('accounts/', include('apps.accounts.urls')),

    # Dashboard related
    path('', include('apps.accounts.dashboard_urls')),  # we will create this
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)