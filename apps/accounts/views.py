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
    from apps.senders.models import Sender
    from apps.campaigns.models import Campaign
    from django.db.models import Sum

    senders_count = Sender.objects.filter(user=request.user, is_active=True).count()
    user_campaigns = Campaign.objects.filter(user=request.user)
    campaigns_count = user_campaigns.count()
    sent_count = user_campaigns.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    recent_campaigns = user_campaigns.order_by('-created_at')[:5]

    context = {
        'senders_count': senders_count,
        'campaigns_count': campaigns_count,
        'sent_count': sent_count,
        'recent_campaigns': recent_campaigns
    }
    return render(request, "dashboard/home.html", context)


@login_required
def settings_view(request):
    return render(request, "dashboard/settings.html")