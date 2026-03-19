from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from .forms import RegisterForm, LoginForm
from django.contrib import messages


def _send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_path = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
    verify_url = request.build_absolute_uri(verify_path)

    subject = 'Verify your Mailexa AI email'
    message = (
        f"Hi {user.get_full_name() or user.email},\n\n"
        "Please verify your email by clicking the link below:\n"
        f"{verify_url}\n\n"
        "If you did not create this account, you can ignore this email.\n\n"
        "— Mailexa AI"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            try:
                _send_verification_email(request, user)
                messages.success(request, "Account created. Verification email sent — please verify your email.")
            except Exception as exc:
                messages.warning(request, f"Account created, but verification email could not be sent: {exc}")
            return redirect("dashboard:dashboard")
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:dashboard")
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
            from django.utils.http import url_has_allowed_host_and_scheme
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('/dashboard/')
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form, "next": request.GET.get('next', '')})

@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("home")


def verify_email_view(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        from .models import User
        user = User.objects.filter(pk=user_id).first()
    except Exception:
        user = None

    if user and default_token_generator.check_token(user, token):
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        messages.success(request, "Your email is verified.")
    else:
        messages.error(request, "Invalid or expired verification link.")

    if request.user.is_authenticated:
        return redirect('dashboard:profile')
    return redirect('accounts:login')


@login_required
def resend_verification_view(request):
    if request.user.email_verified:
        messages.info(request, "Email is already verified.")
        return redirect('dashboard:profile')

    try:
        _send_verification_email(request, request.user)
        messages.success(request, "Verification email sent. Please check your inbox.")
    except Exception as exc:
        messages.error(request, f"Could not send verification email: {exc}")

    return redirect('dashboard:profile')






