from django.conf import settings


def static_version(request):
    return {
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1'),
    }
