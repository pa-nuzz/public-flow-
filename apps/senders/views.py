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
        host = str(data.get('host', '')).strip()
        port = int(data.get('port', 0))
        username = str(data.get('username', '')).strip()
        from_email = str(data.get('from_email', '')).strip()
        password = ''.join(str(data.get('password', '')).split())
        use_tls = bool(data.get('use_tls', True))

        if not host or not password or not port:
            return JsonResponse({'success': False, 'error': 'Missing host, port, username, or password.'})

        # Try multiple auth identities because many providers (especially Gmail)
        # require the account that generated the app password, which may be from_email.
        auth_candidates = []
        if username:
            auth_candidates.append(username)
        if from_email and from_email not in auth_candidates:
            auth_candidates.append(from_email)

        if not auth_candidates:
            return JsonResponse({'success': False, 'error': 'Missing SMTP username/email for authentication.'})

        context = ssl.create_default_context()
        auth_error = None

        def try_login(server):
            # Attempt each candidate in order and keep the last auth error for user feedback.
            nonlocal auth_error
            for candidate in auth_candidates:
                try:
                    server.login(candidate, password)
                    return candidate
                except smtplib.SMTPAuthenticationError as exc:
                    auth_error = exc
                    continue
            raise auth_error or smtplib.SMTPAuthenticationError(535, b'Authentication failed')

        # Port 465 is implicit SSL; non-465 routes can optionally use STARTTLS.
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.ehlo()
                authenticated_as = try_login(server)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                authenticated_as = try_login(server)

        return JsonResponse({'success': True, 'message': f'Connection verified as {authenticated_as}!'})
    except smtplib.SMTPAuthenticationError:
        if 'gmail' in host.lower():
            return JsonResponse({'success': False, 'error': 'Gmail auth failed. Use app password from the same Gmail as SMTP Username (or sender email).'})
        return JsonResponse({'success': False, 'error': 'Authentication failed. Check SMTP username/email and app password.'})
    except smtplib.SMTPConnectError:
        return JsonResponse({'success': False, 'error': 'Unable to connect to SMTP host/port.'})
    except (TimeoutError, smtplib.SMTPServerDisconnected):
        return JsonResponse({'success': False, 'error': 'SMTP connection timed out.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
