from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.senders.models import Sender
from apps.campaigns.models import Campaign
from apps.senders.forms import SenderForm
from .forms import ProfileForm, ChangePasswordForm
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import timedelta

@login_required
def dashboard_view(request):
    user_campaigns = Campaign.objects.filter(user=request.user)
    senders = Sender.objects.filter(user=request.user, is_active=True)
    
    total_sent = user_campaigns.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    total_opens = user_campaigns.aggregate(Sum('open_count'))['open_count__sum'] or 0
    avg_open_rate = round((total_opens / total_sent * 100), 1) if total_sent > 0 else 0
    avg_spam_score = user_campaigns.filter(spam_score__isnull=False).aggregate(Avg('spam_score'))['spam_score__avg']
    
    recent_campaigns = user_campaigns.select_related('sender').order_by('-created_at')[:5]

    status_style_map = {
        'sent': 'bg-emerald-50 text-emerald-600 border-emerald-200',
        'scheduled': 'bg-indigo-50 text-indigo-600 border-indigo-200',
        'sending': 'bg-amber-50 text-amber-700 border-amber-200',
        'draft': 'bg-slate-100 text-slate-700 border-slate-200',
        'failed': 'bg-red-50 text-red-700 border-red-200',
        'paused': 'bg-slate-100 text-slate-700 border-slate-200',
    }

    campaign_rows = []
    for campaign in recent_campaigns:
        campaign_rows.append(
            {
                'name': campaign.name,
                'status': campaign.get_status_display(),
                'status_style': status_style_map.get(campaign.status, status_style_map['draft']),
                'recipients': f"{campaign.total_recipients:,}",
                'open_rate': f"{campaign.open_rate}%" if campaign.sent_count > 0 else '—',
                'date': campaign.created_at.strftime('%b %d, %Y'),
            }
        )

    today = timezone.now().date()
    sent_today = user_campaigns.filter(updated_at__date=today).aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    active_campaigns = user_campaigns.filter(status__in=['sending', 'scheduled']).count()

    kpis = [
        {
            'label': 'Emails Sent Today',
            'value': f"{sent_today:,}",
            'change': 'Live',
            'trend': 'up',
            'icon_bg': 'bg-indigo-50 text-indigo-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4h16v16H4z"/><polyline points="22,6 12,13 2,6"/></svg>',
        },
        {
            'label': 'Open Rate',
            'value': f"{avg_open_rate}%",
            'change': 'Overall',
            'trend': 'up',
            'icon_bg': 'bg-emerald-50 text-emerald-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="4 14 8 10 12 14 20 6"/></svg>',
        },
        {
            'label': 'Spam Safety',
            'value': f"{round(avg_spam_score, 1) if avg_spam_score else 0}/100",
            'change': 'AI Score',
            'trend': 'up' if (avg_spam_score or 0) >= 60 else 'down',
            'icon_bg': 'bg-indigo-50 text-indigo-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 3l7 4v5c0 5-3.5 9-7 9s-7-4-7-9V7l7-4z"/></svg>',
        },
        {
            'label': 'Active Campaigns',
            'value': str(active_campaigns),
            'change': 'Current',
            'trend': 'up',
            'icon_bg': 'bg-emerald-50 text-emerald-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
        },
    ]

    chart_data = []
    max_sent = 1
    max_open = 1
    day_buckets = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_qs = user_campaigns.filter(created_at__date=day)
        sent = day_qs.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
        opens = day_qs.aggregate(Sum('open_count'))['open_count__sum'] or 0
        max_sent = max(max_sent, sent)
        max_open = max(max_open, opens)
        day_buckets.append((day, sent, opens))

    for day, sent, opens in day_buckets:
        chart_data.append(
            {
                'day': day.strftime('%a'),
                'sent': sent,
                'opens': opens,
                'sent_pct': round((sent / max_sent) * 100) if max_sent else 0,
                'opens_pct': round((opens / max_open) * 100) if max_open else 0,
            }
        )

    weekly_stats = [
        {
            'label': 'Total Sent',
            'value': f"{total_sent:,}",
            'width': '100%',
            'color': 'bg-indigo-500',
        },
        {
            'label': 'Total Opened',
            'value': f"{total_opens:,}",
            'width': f"{int((total_opens / total_sent) * 100) if total_sent else 0}%",
            'color': 'bg-emerald-400',
        },
        {
            'label': 'Bounced',
            'value': f"{(user_campaigns.aggregate(Sum('bounce_count'))['bounce_count__sum'] or 0):,}",
            'width': f"{int(((user_campaigns.aggregate(Sum('bounce_count'))['bounce_count__sum'] or 0) / total_sent) * 100) if total_sent else 0}%",
            'color': 'bg-rose-400',
        },
        {
            'label': 'Senders',
            'value': str(senders.count()),
            'width': f"{min(100, senders.count() * 10)}%",
            'color': 'bg-slate-400',
        },
    ]

    context = {
        'kpis': kpis,
        'chart_data': chart_data,
        'weekly_stats': weekly_stats,
        'campaigns': campaign_rows,
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def settings_view(request):
    senders = Sender.objects.filter(user=request.user)
    sender_form = SenderForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_sender':
            sender_form = SenderForm(request.POST)

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