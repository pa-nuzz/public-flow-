from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import RegisterForm, LoginForm


# -------------------
# AUTH
# -------------------

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("dashboard")
    else:
        form = LoginForm()

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


# -------------------
# DASHBOARD
# -------------------

@login_required
def dashboard_view(request):
    # Mock data for now to ensure dashboard works
    context = {
        'senders_count': 0,
        'campaigns_count': 0,
        'sent_count': 0,
        'recent_campaigns': []
    }
    return render(request, "dashboard/home.html", context)


@login_required
def settings_view(request):
    return render(request, "dashboard/settings.html")