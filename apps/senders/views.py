from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import smtplib, ssl, json

# Create your views here.

@login_required
@require_POST
def verify_sender(request):
    try:
        data = json.loads(request.body)
        context = ssl.create_default_context()
        with smtplib.SMTP(data['host'], int(data['port']), timeout=10) as server:
            server.ehlo()
            if data.get('use_tls'):
                server.starttls(context=context)
            server.login(data['username'], data['password'])
        return JsonResponse({'success': True, 'message': 'Connection verified!'})
    except smtplib.SMTPAuthenticationError:
        return JsonResponse({'success': False, 'error': 'Authentication failed. Check username/password.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
