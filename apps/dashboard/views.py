from django.contrib.auth.decorators import login_required
"""Dashboard views module.

Provides views for rendering the main dashboard with KPIs, email engagement metrics,
campaign statistics, and user profile/settings management.
"""

from datetime import datetime, timedelta
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
    """Render the main dashboard with KPIs, engagement metrics, and campaign summaries.
    
    This view aggregates email engagement data from the EmailEngagement model and calculates
    week-over-week deltas for key performance indicators (KPIs). It also prepares chart data
    for daily email sent/open visualization and recent campaign details.
    
    Args:
        request: The HTTP request object containing the authenticated user.
    
    Returns:
        HttpResponse: Rendered dashboard template with KPI and chart context data.
    """
    # Fetch user-specific campaigns, engagements, and active senders
    user_campaigns = Campaign.objects.filter(user=request.user)
    user_engagements = EmailEngagement.objects.filter(campaign__user=request.user)
    senders = Sender.objects.filter(user=request.user, is_active=True)

    # Calculate date ranges: current week (last 7 days) and previous week
    today = timezone.now().date()
    week_start = today - timedelta(days=6)  # 7 days starting from 6 days ago
    prev_week_start = week_start - timedelta(days=7)  # Previous 7-day period
    prev_week_end = week_start - timedelta(days=1)  # Last day of previous week

    # Determine if timezone-aware operations are needed
    now_value = timezone.now()
    timezone_aware = timezone.is_aware(now_value)

    def day_bounds(day):
        """Calculate timezone-safe start and end datetime for a calendar day.
        
        This helper ensures that email aggregation works correctly across timezone
        boundaries. Date filters using __date would fail on DST transitions.
        
        Args:
            day: A date object representing the calendar day.
        
        Returns:
            tuple: (start_datetime, end_datetime) for the calendar day, timezone-aware if needed.
        """
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        if timezone_aware:
            tz = timezone.get_current_timezone()
            start = timezone.make_aware(start, tz)
            end = timezone.make_aware(end, tz)
        return start, end

    # Pre-calculate datetime boundaries for week and previous week filtering
    week_start_dt, _ = day_bounds(week_start)
    _, tomorrow_dt = day_bounds(today)  # End of today (start of tomorrow)
    prev_week_start_dt, _ = day_bounds(prev_week_start)
    _, prev_week_end_next_dt = day_bounds(prev_week_end)

    # Fetch 5 most recent campaigns for display in dashboard summary
    recent_campaigns = user_campaigns.select_related('sender').order_by('-created_at')[:5]

    # Map campaign statuses to Tailwind CSS styling classes for UI consistency
    status_style_map = {
        'sent': 'bg-emerald-50 text-emerald-600 border-emerald-200',
        'scheduled': 'bg-indigo-50 text-indigo-600 border-indigo-200',
        'sending': 'bg-amber-50 text-amber-700 border-amber-200',
        'draft': 'bg-slate-100 text-slate-700 border-slate-200',
        'failed': 'bg-red-50 text-red-700 border-red-200',
        'paused': 'bg-slate-100 text-slate-700 border-slate-200',
    }

    # Transform campaign objects into display rows with formatted data
    campaign_rows = []
    for campaign in recent_campaigns:
        # Localize campaign creation datetime for proper display in user's timezone
        campaign_created_at = timezone.localtime(campaign.created_at) if timezone.is_aware(campaign.created_at) else campaign.created_at
        campaign_rows.append(
            {
                'name': campaign.name,
                'status': campaign.status.title(),
                'status_style': status_style_map.get(campaign.status, status_style_map['draft']),
                'recipients': f"{campaign.total_recipients:,}",
                'open_rate': f"{campaign.open_rate}%" if campaign.sent_count > 0 else '—',
                'date': campaign_created_at.strftime('%b %d, %Y'),
            }
        )

    # Fetch weekly data (current 7-day period) using timezone-safe datetime ranges
    weekly_campaigns = user_campaigns.filter(updated_at__gte=week_start_dt, updated_at__lt=tomorrow_dt)
    weekly_engagements = user_engagements.filter(
        sent_at__gte=week_start_dt,
        sent_at__lt=tomorrow_dt,
    )

    # Calculate this week's KPIs from EmailEngagement events (event-driven, not denormalized counts)
    weekly_sent = weekly_engagements.count()
    weekly_bounced = weekly_campaigns.aggregate(Sum('bounce_count'))['bounce_count__sum'] or 0
    weekly_opened = weekly_engagements.filter(opened_at__isnull=False).count()  # Emails with first_open tracked
    weekly_clicked = weekly_engagements.filter(clicked_at__isnull=False).count()  # Emails with first_click tracked
    weekly_open_rate = round((weekly_opened / weekly_sent * 100), 1) if weekly_sent > 0 else 0
    weekly_spam_score = weekly_campaigns.filter(spam_score__isnull=False).aggregate(Avg('spam_score'))['spam_score__avg'] or 0

    # Fetch previous week's data for delta (week-over-week comparison) calculations
    prev_weekly_campaigns = user_campaigns.filter(updated_at__gte=prev_week_start_dt, updated_at__lt=prev_week_end_next_dt)
    prev_weekly_engagements = user_engagements.filter(
        sent_at__gte=prev_week_start_dt,
        sent_at__lt=prev_week_end_next_dt,
    )
    prev_weekly_sent = prev_weekly_engagements.count()
    prev_weekly_opened = prev_weekly_engagements.filter(opened_at__isnull=False).count()
    prev_weekly_clicked = prev_weekly_engagements.filter(clicked_at__isnull=False).count()
    prev_open_rate = round((prev_weekly_opened / prev_weekly_sent * 100), 1) if prev_weekly_sent > 0 else 0
    prev_spam_score = prev_weekly_campaigns.filter(spam_score__isnull=False).aggregate(Avg('spam_score'))['spam_score__avg'] or 0
    prev_active_campaigns = prev_weekly_campaigns.filter(status__in=['sending', 'scheduled']).count()

    def fmt_delta(current, previous, suffix=''):
        """Format delta changes for KPI display with trend indicator.
        
        Converts week-over-week changes into a human-readable format with up/down trend.
        
        Args:
            current (float): Current period value.
            previous (float): Previous period value for comparison.
            suffix (str): Optional suffix (e.g., '%' for percentages).
        
        Returns:
            tuple: (formatted_delta_str, trend_direction) where trend is 'up' or 'down'.
        """
        if previous == 0:
            if current == 0:
                return '0' + suffix, 'up'
            return f'+{current}{suffix}', 'up'
        delta = current - previous
        trend = 'up' if delta >= 0 else 'down'
        sign = '+' if delta >= 0 else ''
        return f'{sign}{delta}{suffix}', trend

    # Calculate all-time totals and today's metrics
    total_sent = user_engagements.count()
    total_opened = user_engagements.filter(opened_at__isnull=False).count()
    today_start_dt, today_end_dt = day_bounds(today)
    sent_today = user_engagements.filter(sent_at__gte=today_start_dt, sent_at__lt=today_end_dt).count()
    active_campaigns = user_campaigns.filter(status__in=['sending', 'scheduled']).count()

    # Calculate week-over-week deltas for all KPIs
    sent_delta, sent_trend = fmt_delta(weekly_sent, prev_weekly_sent)
    open_delta, open_trend = fmt_delta(weekly_open_rate, prev_open_rate, '%')
    click_delta, click_trend = fmt_delta(weekly_clicked, prev_weekly_clicked)
    spam_delta, spam_trend = fmt_delta(round(weekly_spam_score or 0, 1), round(prev_spam_score or 0, 1))
    active_delta, active_trend = fmt_delta(active_campaigns, prev_active_campaigns)

    # Build KPI card data structure for frontend rendering with styling and SVG icons
    kpis = [
        {  # KPI 1: Emails Sent (Last 7 Days)
            'label': 'Emails Sent (Last 7 Days)',
            'value': f"{weekly_sent:,}",
            'change': sent_delta,
            'trend': sent_trend,
            'period_label': 'vs previous 7 days',
            'icon_bg': 'bg-indigo-50 text-indigo-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4h16v16H4z"/><polyline points="22,6 12,13 2,6"/></svg>',
        },
        {
            'label': 'Open Rate (Last 7 Days)',
            'value': f"{weekly_open_rate}%",
            'change': open_delta,
            'trend': open_trend,
            'period_label': 'vs previous 7 days',
            'icon_bg': 'bg-emerald-50 text-emerald-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="4 14 8 10 12 14 20 6"/></svg>',
        },
        {
            'label': 'Clicks (Last 7 Days)',
            'value': f"{weekly_clicked:,}",
            'change': click_delta,
            'trend': click_trend,
            'period_label': 'vs previous 7 days',
            'icon_bg': 'bg-indigo-50 text-indigo-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10 13a5 5 0 007.54.54l3.92-3.91a5 5 0 00-7.07-7.08l-1.77 1.77"/><path d="M14 11a5 5 0 00-7.54-.54L2.54 14.37a5 5 0 107.07 7.08l1.77-1.77"/></svg>',
        },
        {
            'label': 'Active Campaigns',
            'value': str(active_campaigns),
            'change': active_delta,
            'trend': active_trend,
            'period_label': 'vs previous 7 days',
            'icon_bg': 'bg-emerald-50 text-emerald-600',
            'icon_svg': '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
        },
    ]

    # Build chart data for 7-day trend visualization using timezone-safe day bucketing
    chart_data = []
    max_sent = 1  # Minimum value to avoid division by zero
    max_open = 1
    day_buckets = []
    # Aggregate engagement counts by calendar day (backward from today)
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_start_dt, day_end_dt = day_bounds(day)  # Get timezone-safe boundaries
        sent = user_engagements.filter(sent_at__gte=day_start_dt, sent_at__lt=day_end_dt).count()
        opens = user_engagements.filter(opened_at__gte=day_start_dt, opened_at__lt=day_end_dt).count()
        max_sent = max(max_sent, sent)
        max_open = max(max_open, opens)
        day_buckets.append((day, sent, opens))

    # Transform bucket data into chart display format with percentage calculations
    for day, sent, opens in day_buckets:
        chart_data.append(
            {
                'day': day.strftime('%a'),  # Day of week abbreviation (Mon, Tue, etc.)
                'date_label': day.strftime('%b %d'),  # Date label for tooltip (Mar 19)
                'sent': sent,
                'opens': opens,
                'sent_pct': round((sent / max_sent) * 100) if max_sent else 0,  # Percentage for bar height
                'opens_pct': round((opens / max_open) * 100) if max_open else 0,
            }
        )

    # Determine max value for weekly stats bar width scaling
    max_weekly_value = max(weekly_sent, weekly_opened, weekly_bounced, senders.count(), weekly_clicked, 1)
    # Calculate deliverability rate (percentage of emails successfully delivered)
    deliverability_rate = round(((weekly_sent - weekly_bounced) / weekly_sent) * 100, 1) if weekly_sent else 0.0

    # Build weekly statistics bars for sidebar visualization
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

    # Compile all dashboard data into context dictionary for template rendering
    context = {
        'kpis': kpis,  # Key performance indicators with deltas
        'chart_data': chart_data,  # 7-day sent/open trend data
        'weekly_stats': weekly_stats,  # Weekly bar chart stats
        'campaigns': campaign_rows,  # Recent campaign summaries
        'inbox_rate': deliverability_rate,  # Percentage of emails delivered
        'total_sent': total_sent,  # All-time total emails sent
        'total_opened': total_opened,  # All-time total emails opened
        'weekly_clicked': weekly_clicked,  # This week's total clicks
        'sent_today': sent_today,  # Emails sent today
        'weekly_spam_score': round(weekly_spam_score, 1) if weekly_spam_score else 0,  # Weekly avg spam score
        'spam_delta': spam_delta,  # Week-over-week spam score change
        'spam_trend': spam_trend,  # Spam score trend direction
        'weekly_clicked_width': int((weekly_clicked / max_weekly_value) * 100) if max_weekly_value else 0,  # Bar % width
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def settings_view(request):
    """Manage sender SMTP profiles and email credentials.
    
    Allows users to add, update, and delete SMTP sender profiles for outgoing emails.
    Email normalization and deduplication prevent duplicate sender configurations.
    
    Args:
        request: The HTTP request object containing the authenticated user.
    
    Returns:
        HttpResponse: Rendered settings template with senders list and form.
    """
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
    """Manage user profile and password settings.
    
    Allows users to update avatar, company info, and change their password.
    Also displays total sent campaigns count.
    
    Args:
        request: The HTTP request object containing the authenticated user.
    
    Returns:
        HttpResponse: Rendered profile template with user forms and campaign count.
    """
    profile_form = ProfileForm(instance=request.user)
    password_form = ChangePasswordForm(request.user)
    total_campaigns = Campaign.objects.filter(user=request.user, status='sent').count()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('dashboard:dashboard')

        elif action == 'change_password':
            password_form = ChangePasswordForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Password changed. Please log in again.')
                return redirect('accounts:login')

    return render(request, 'dashboard/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'total_campaigns': total_campaigns,
    })


@login_required
def clear_notifications_view(request):
    """Clear dashboard notification dismissal timestamp via AJAX.
    
    Records when user dismissed dashboard notifications to control re-display.
    
    Args:
        request: The HTTP request object with POST method.
    
    Returns:
        JsonResponse: JSON response with status confirmation.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    request.session['dashboard_notifications_dismissed_at'] = timezone.now().isoformat()
    request.session.modified = True
    return JsonResponse({'ok': True})


@login_required
def templates_view(request):
    """Render email templates management page.
    
    Currently a placeholder for future template management functionality.
    
    Args:
        request: The HTTP request object containing the authenticated user.
    
    Returns:
        HttpResponse: Rendered templates page.
    """
    return render(request, 'dashboard/templates_page.html', {'templates': []})