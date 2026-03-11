from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from .forms import RegisterForm, LoginForm
from django.contrib import messages

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully!")
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
    return redirect("accounts:login")






