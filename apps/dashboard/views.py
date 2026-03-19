from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.campaigns.models import Campaign, EmailEngagement
from apps.senders.forms import SenderForm
from apps.senders.models import Sender

from .forms import ChangePasswordForm, ProfileForm


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
                'status': campaign.status.title(),
                'status_style': status_style_map.get(campaign.status, status_style_map['draft']),
                'recipients': f"{campaign.total_recipients:,}",
                'open_rate': f"{campaign.open_rate}%" if campaign.sent_count > 0 else '—',
                'date': campaign.created_at.strftime('%b %d, %Y'),
            }
        )

    today = timezone.now().date()
    week_start = today - timedelta(days=6)

    weekly_campaigns = user_campaigns.filter(updated_at__date__gte=week_start, updated_at__date__lte=today)
    weekly_engagements = EmailEngagement.objects.filter(
        campaign__user=request.user,
        sent_at__date__gte=week_start,
        sent_at__date__lte=today,
    )

    weekly_sent = weekly_campaigns.aggregate(Sum('sent_count'))['sent_count__sum'] or 0
    weekly_bounced = weekly_campaigns.aggregate(Sum('bounce_count'))['bounce_count__sum'] or 0
    weekly_opened = weekly_engagements.filter(opened_at__isnull=False).count()
    weekly_clicked = weekly_engagements.filter(clicked_at__isnull=False).count()

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
        opens = EmailEngagement.objects.filter(
            campaign__user=request.user,
            opened_at__date=day,
        ).count()
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

    max_weekly_value = max(weekly_sent, weekly_opened, weekly_bounced, senders.count(), weekly_clicked, 1)
    deliverability_rate = round(((weekly_sent - weekly_bounced) / weekly_sent) * 100, 1) if weekly_sent else 0.0

    weekly_stats = [
        {
            'label': 'Total Sent',
            'value': f"{weekly_sent:,}",
            'width': f"{int((weekly_sent / max_weekly_value) * 100)}%",
            'color': 'bg-indigo-500',
        },
        {
            'label': 'Total Opened',
            'value': f"{weekly_opened:,}",
            'width': f"{int((weekly_opened / max_weekly_value) * 100)}%",
            'color': 'bg-emerald-400',
        },
        {
            'label': 'Bounced',
            'value': f"{weekly_bounced:,}",
            'width': f"{int((weekly_bounced / max_weekly_value) * 100)}%",
            'color': 'bg-rose-400',
        },
        {
            'label': 'Senders',
            'value': str(senders.count()),
            'width': f"{int((senders.count() / max_weekly_value) * 100)}%",
            'color': 'bg-slate-400',
        },
    ]

    context = {
        'kpis': kpis,
        'chart_data': chart_data,
        'weekly_stats': weekly_stats,
        'campaigns': campaign_rows,
        'inbox_rate': deliverability_rate,
        'weekly_clicked': weekly_clicked,
        'weekly_clicked_width': int((weekly_clicked / max_weekly_value) * 100) if max_weekly_value else 0,
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
                candidate = sender_form.save(commit=False)
                normalized_email = (candidate.from_email or '').strip().lower()
                existing_sender = Sender.objects.filter(
                    user=request.user,
                    from_email__iexact=normalized_email,
                ).first()

                if existing_sender:
                    existing_sender.display_name = candidate.display_name
                    existing_sender.from_email = normalized_email
                    existing_sender.provider = candidate.provider
                    existing_sender.smtp_host = candidate.smtp_host
                    existing_sender.smtp_port = candidate.smtp_port
                    existing_sender.username = candidate.username
                    existing_sender.use_tls = candidate.use_tls
                    existing_sender.daily_limit = candidate.daily_limit
                    existing_sender.is_active = True

                    raw_password = sender_form.cleaned_data.get('smtp_password')
                    if raw_password:
                        existing_sender.set_password(raw_password)

                    existing_sender.save()
                    messages.success(request, 'Sender already existed and was updated successfully.')
                else:
                    sender = candidate
                    sender.user = request.user
                    sender.from_email = normalized_email
                    raw_password = sender_form.cleaned_data['smtp_password']
                    sender.set_password(raw_password)
                    sender.save()
                    messages.success(request, 'Sender added successfully.')

                return redirect('dashboard:settings')

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


@login_required
def clear_notifications_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    request.session['dashboard_notifications_dismissed_at'] = timezone.now().isoformat()
    request.session.modified = True
    return JsonResponse({'ok': True})