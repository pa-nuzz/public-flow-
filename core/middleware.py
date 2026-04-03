import os
import sys


class DevHTTPMiddleware:
    """
    Middleware to disable HTTPS/HSTS in development to prevent browser caching issues.
    Removes HSTS headers to prevent SSL redirect on localhost/127.0.0.1.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.debug = os.getenv('DEBUG', 'False') == 'True'

    def __call__(self, request):
        response = self.get_response(request)
        
        if self.debug or 'runserver' in sys.argv:
            # Remove HSTS headers to prevent browser from caching HTTPS-only policy
            # Do NOT clear cookies - that breaks CSRF protection
            if 'Strict-Transport-Security' in response:
                del response['Strict-Transport-Security']
        
        return response


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.tailwindcss.com https://fonts.googleapis.com 'unsafe-inline'; "
            "style-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )
        return response