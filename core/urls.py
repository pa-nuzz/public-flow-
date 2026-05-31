from django.contrib import admin
import core.admin  # ensure admin site branding is applied
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_view, name='home'),
    path('senders/', include('apps.senders.urls', namespace='senders')),
    path('contacts/', include('apps.contacts.urls', namespace='contacts')),
    path('campaign/', include('apps.campaigns.urls', namespace='campaigns')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('intelligence/', include('apps.intelligence.urls', namespace='intelligence')),
    path('automations/', include('apps.automations.urls', namespace='automations')),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt',
        content_type='text/plain'
    ), name='robots_txt'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


