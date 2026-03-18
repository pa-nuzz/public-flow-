from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.senders.models import Sender
from apps.campaigns.models import Campaign
from apps.senders.forms import SenderForm
from .forms import ProfileForm, ChangePasswordForm
from django.db.models import Sum, Avg
from django.utils import timezone

@login_required
def dashboard_view(request):
    user_campaigns = Campaign.objects.filter(user=request.user)
    senders = Sender.objects.filter(user=request.user, is_active=True)
    
    total_sent = user_campaigns.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    total_opens = user_campaigns.aggregate(Sum('open_count'))['open_count__sum'] or 0
    avg_open_rate = round((total_opens / total_sent * 100), 1) if total_sent > 0 else 0
    avg_spam_score = user_campaigns.filter(spam_score__isnull=False).aggregate(Avg('spam_score'))['spam_score__avg']
    
    recent_campaigns = user_campaigns.select_related('sender').order_by('-created_at')[:5]
    
    context = {
        'campaigns_count': user_campaigns.count(),
        'sent_count': total_sent,
        'avg_open_rate': avg_open_rate,
        'avg_spam_score': round(avg_spam_score, 1) if avg_spam_score else None,
        'senders_count': senders.count(),
        'recent_campaigns': recent_campaigns,
        'draft_count': user_campaigns.filter(status='draft').count(),
        'active_count': user_campaigns.filter(status__in=['sending', 'scheduled']).count(),
    }
    return render(request, "dashboard/home.html", context)


@login_required
def settings_view(request):
    senders = Sender.objects.filter(user=request.user)
    sender_form = SenderForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_sender':
            sender_form = SenderForm(request.POST)

            if not sender_form.is_valid():
                print(f"Form errors: {sender_form.errors}")  # Debug

            if sender_form.is_valid():
                sender = sender_form.save(commit=False)
                sender.user = request.user
                raw_password = sender_form.cleaned_data['smtp_password']
                sender.set_password(raw_password)
                sender.save()
                messages.success(request, 'Sender added successfully.')
                return redirect('dashboard:settings')
            else:
                messages.error(request, 'Please correct the errors below.')
        elif action == 'delete_sender':
            sender_id = request.POST.get('sender_id')
            Sender.objects.filter(id=sender_id, user=request.user).delete()
            messages.success(request, 'Sender removed.')
            return redirect('dashboard:settings')

    context = {'senders': senders, 'sender_form': sender_form}
    return render(request, 'dashboard/settings.html', context)


@login_required
def profile_view(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = ChangePasswordForm(request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('dashboard:profile')
        elif action == 'change_password':
            password_form = ChangePasswordForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Password changed. Please log in again.')
                return redirect('accounts:login')
    
    return render(request, 'dashboard/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })

kpis = [
    {
        "label": "Emails Sent Today",
        "value": "48,291",
        "change": "+12.4%",
        "trend": "up",
        "icon_bg": "bg-indigo-50 text-indigo-600",
        "icon_svg": '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4h16v16H4z"/><polyline points="22,6 12,13 2,6"/></svg>',
    },
    {
        "label": "Open Rate",
        "value": "38.7%",
        "change": "+2.1%",
        "trend": "up",
        "icon_bg": "bg-emerald-50 text-emerald-600",
        "icon_svg": '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="4 14 8 10 12 14 20 6"/></svg>',
    },
    {
        "label": "Click-Through Rate",
        "value": "6.2%",
        "change": "-0.4%",
        "trend": "down",
        "icon_bg": "bg-indigo-50 text-indigo-600",
        "icon_svg": '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M5 12l5 5L20 7"/></svg>',
    },
    {
        "label": "Active Campaigns",
        "value": "14",
        "change": "+3 this week",
        "trend": "up",
        "icon_bg": "bg-emerald-50 text-emerald-600",
        "icon_svg": '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    },
]


chart_data = [
    {"day": "Mon", "sent": 6000, "opens": 2200, "sent_pct": 60, "opens_pct": 25},
    {"day": "Tue", "sent": 8500, "opens": 3000, "sent_pct": 80, "opens_pct": 35},
    {"day": "Wed", "sent": 7200, "opens": 2800, "sent_pct": 70, "opens_pct": 30},
    {"day": "Thu", "sent": 9100, "opens": 4200, "sent_pct": 90, "opens_pct": 45},
    {"day": "Fri", "sent": 10400, "opens": 4600, "sent_pct": 100, "opens_pct": 50},
    {"day": "Sat", "sent": 5400, "opens": 1900, "sent_pct": 50, "opens_pct": 20},
    {"day": "Sun", "sent": 6100, "opens": 2100, "sent_pct": 55, "opens_pct": 22},
]

weekly_stats = [
    {
        "label": "Total Sent",
        "value": "52,600",
        "width": "100%",
        "color": "bg-indigo-500",
    },
    {
        "label": "Total Opened",
        "value": "20,702",
        "width": "40%",
        "color": "bg-emerald-400",
    },
    {
        "label": "Bounced",
        "value": "312",
        "width": "5%",
        "color": "bg-rose-400",
    },
    {
        "label": "Unsubscribed",
        "value": "47",
        "width": "2%",
        "color": "bg-slate-400",
    },
]

campaigns = [
    {
        "name": "Q4 Product Launch",
        "status": "Sent",
        "status_style": "bg-emerald-50 text-emerald-600 border-emerald-200",
        "recipients": "12,400",
        "open_rate": "41.2%",
        "date": "Feb 16, 2025",
    },
    {
        "name": "Weekly Newsletter #48",
        "status": "Sent",
        "status_style": "bg-emerald-50 text-emerald-600 border-emerald-200",
        "recipients": "8,900",
        "open_rate": "35.8%",
        "date": "Feb 14, 2025",
    },
    {
        "name": "Spring Promo",
        "status": "Scheduled",
        "status_style": "bg-indigo-50 text-indigo-600 border-indigo-200",
        "recipients": "22,100",
        "open_rate": "—",
        "date": "Feb 20, 2025",
    },
    {
        "name": "Re-engagement Flow",
        "status": "Scheduled",
        "status_style": "bg-indigo-50 text-indigo-600 border-indigo-200",
        "recipients": "22,100",
        "open_rate": "—",
        "date": "Feb 20, 2025",
    },
    {
        "name": "Onboarding Series v3",
        "status": "Scheduled",
        "status_style": "bg-indigo-50 text-indigo-600 border-indigo-200",
        "recipients": "22,100",
        "open_rate": "—",
        "date": "Feb 20, 2025",
    },
]

from django.shortcuts import render

def dashboard_view(request):

    # paste all lists here
    context = {
        "kpis": kpis,
        "chart_data": chart_data,
        "weekly_stats": weekly_stats,
        "campaigns": campaigns,
    }

    return render(request, "dashboard/home.html", context)