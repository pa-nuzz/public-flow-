from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
from apps.senders.models import Sender
from apps.campaigns.models import Campaign
from django.db.models import Sum
@login_required
def dashboard_view(request):
    

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

