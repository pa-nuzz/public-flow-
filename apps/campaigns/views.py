"""Campaign management views module.

Provides views for creating, editing, sending, and tracking email campaigns.
Includes SMTP sending, tracking pixel handling, and click redirect tracking.
"""

import base64
import csv
from datetime import timedelta
from urllib.parse import unquote_plus, urlparse

from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncHour
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from apps.senders.models import Sender
from .models import Campaign, EmailClickEvent, EmailEngagement
from .forms import CampaignForm
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib import messages
from apps.contacts.models import ContactList, Contact, ContactTag
from .services import (
    text_to_html,
    apply_campaign_spam_signals,
    merge_recipient_emails,
    send_campaign_with_smtp,
    send_test_email_with_smtp,
    update_campaign_unique_open_count,
)


def _validate_campaign_ready_to_send(campaign_obj):
    errors = []
    if not campaign_obj.sender_id:
        errors.append('Select a sender profile before sending.')
    if not (campaign_obj.subject or '').strip():
        errors.append('Subject is required before sending.')
    if not (campaign_obj.body_text or '').strip():
        errors.append('Message content is required before sending.')
    recipient_count = len(campaign_obj.get_recipient_list())
    if recipient_count == 0:
        errors.append('Add at least one valid recipient email before sending.')
    return errors, recipient_count


def _campaign_form_view(request, campaign=None, read_only=False):
    """Internal helper for campaign creation, editing, and viewing.
    
    Handles the form submission logic for campaigns. Supports three modes:
    - Create new campaign (campaign=None, read_only=False)
    - Edit existing campaign (campaign=obj, read_only=False)
    - View existing campaign (campaign=obj, read_only=True)
    
    When sending immediately, calls send_campaign_with_smtp and accumulates sent_count
    across multiple sends to the same campaign. Merge contact list emails with manually
    entered recipient_emails to support both input methods.
    
    Args:
        request: The HTTP request object with optional POST data.
        campaign (Campaign, optional): Existing campaign to edit/view, or None for new.
        read_only (bool): If True, render form with all fields disabled for viewing.
    
    Returns:
        HttpResponse: Rendered campaign form template with context data.
    """
    # Fetch user's active SMTP senders for form dropdown
    senders = Sender.objects.filter(user=request.user, is_active=True)

    # Read-only mode: display campaign data with all fields disabled
    if read_only:
        form = CampaignForm(user=request.user, instance=campaign)
        for _, field in form.fields.items():
            field.disabled = True
        return render(request, 'campaigns/create.html', {
            'form': form,
            'senders': senders,
            'campaign': campaign,
            'contact_lists': ContactList.objects.filter(user=request.user),
            'read_only': True,
        })

    # Form submission: process POST request
    if request.method == 'POST':
        form = CampaignForm(request.POST, user=request.user, instance=campaign)
        action = request.POST.get('action', 'save_draft')  # 'save_draft' or 'send_now'

        if form.is_valid():
            campaign_obj = form.save(commit=False)  # Don't save to DB yet
            campaign_obj.user = request.user
            # Convert plain text body to HTML for email rendering
            campaign_obj.body_html = text_to_html(campaign_obj.body_text or '')
            # Apply spam filter heuristics and calculate spam score
            apply_campaign_spam_signals(campaign_obj)

            # Merge selected saved list emails and optional tag-segmented contacts.
            selected_list_ids = [value for value in request.POST.getlist('contact_lists') if value.isdigit()]
            selected_tag_ids = [value for value in request.POST.getlist('contact_tags') if value.isdigit()]

            if selected_list_ids:
                selected_lists = ContactList.objects.filter(user=request.user, id__in=selected_list_ids)
                if selected_tag_ids:
                    tagged_emails = Contact.objects.filter(
                        contact_list__in=selected_lists,
                        is_active=True,
                        tags__id__in=selected_tag_ids,
                    ).values_list('email', flat=True).distinct()
                    campaign_obj.recipient_emails = merge_recipient_emails(
                        campaign_obj.recipient_emails,
                        list(tagged_emails),
                    )
                else:
                    for selected_list in selected_lists:
                        campaign_obj.recipient_emails = merge_recipient_emails(
                            campaign_obj.recipient_emails,
                            selected_list.get_email_list(),
                        )
            elif selected_tag_ids:
                tagged_emails = Contact.objects.filter(
                    contact_list__user=request.user,
                    is_active=True,
                    tags__id__in=selected_tag_ids,
                ).values_list('email', flat=True).distinct()
                campaign_obj.recipient_emails = merge_recipient_emails(
                    campaign_obj.recipient_emails,
                    list(tagged_emails),
                )

            # Backward compatibility for older single-list input.
            contact_list = form.cleaned_data.get('contact_list')
            if contact_list:
                campaign_obj.recipient_emails = merge_recipient_emails(campaign_obj.recipient_emails, contact_list.get_email_list())

            if action == 'send_test':
                test_email = (request.POST.get('test_email') or '').strip().lower()
                if not test_email:
                    messages.error(request, 'Enter a test email address before sending a test.')
                    return render(request, 'campaigns/create.html', {
                        'form': form,
                        'senders': senders,
                        'campaign': campaign,
                        'contact_lists': ContactList.objects.filter(user=request.user),
                        'available_tags': ContactTag.objects.filter(user=request.user),
                    })
                try:
                    validate_email(test_email)
                except ValidationError:
                    messages.error(request, 'Enter a valid test email address.')
                    return render(request, 'campaigns/create.html', {
                        'form': form,
                        'senders': senders,
                        'campaign': campaign,
                        'contact_lists': ContactList.objects.filter(user=request.user),
                        'available_tags': ContactTag.objects.filter(user=request.user),
                    })

                campaign_obj.total_recipients = len(campaign_obj.get_recipient_list())
                if not campaign_obj.pk:
                    campaign_obj.status = 'draft'
                campaign_obj.save()
                try:
                    send_test_email_with_smtp(campaign_obj, test_email)
                    messages.success(request, f'Test email sent to {test_email}.')
                except Exception as exc:
                    messages.error(request, f'Test send failed: {exc}')
                return redirect('campaigns:campaign_edit', campaign_id=campaign_obj.id)

            # Handle "Send Now" action: immediately send campaign via SMTP
            if action == 'send_now':
                pre_send_errors, recipient_count = _validate_campaign_ready_to_send(campaign_obj)
                if pre_send_errors:
                    for error in pre_send_errors:
                        messages.error(request, error)
                    campaign_obj.status = 'draft'
                    campaign_obj.total_recipients = recipient_count
                    campaign_obj.save()
                    return redirect('campaigns:campaign_edit', campaign_id=campaign_obj.id)

                campaign_obj.status = 'sending'  # Temp status during send
                campaign_obj.total_recipients = recipient_count
                campaign_obj.save()  # Save first to get ID for tracking
                try:
                    # Build tracking base URL for open/click tracking pixel and links
                    base_url = (settings.TRACKING_BASE_URL or request.build_absolute_uri('/')).rstrip('/')
                    sent_count, failed_count, last_error = send_campaign_with_smtp(campaign_obj, base_url)
                    # Accumulate sent_count (don't overwrite) to support re-sends
                    campaign_obj.sent_count = (campaign_obj.sent_count or 0) + sent_count
                    campaign_obj.bounce_count = (campaign_obj.bounce_count or 0) + failed_count
                    campaign_obj.status = 'sent' if campaign_obj.sent_count > 0 else 'failed'
                    campaign_obj.save(update_fields=['sent_count', 'bounce_count', 'status', 'updated_at'])
                    if failed_count > 0:
                        messages.warning(request, f'Campaign sent with partial failures. Sent: {sent_count}, failed: {failed_count}. {last_error or ""}'.strip())
                    else:
                        messages.success(request, f'Campaign "{campaign_obj.name}" sent successfully to {sent_count} recipients.')
                    return redirect('campaigns:campaign_list')
                except Exception as exc:
                    campaign_obj.status = 'failed'
                    campaign_obj.save(update_fields=['status', 'updated_at'])
                    messages.error(request, f'Campaign send failed: {exc}')
                    return redirect('campaigns:campaign_edit', campaign_id=campaign_obj.id)

            # Handle "Save Draft" action: save without sending
            campaign_obj.status = 'scheduled' if campaign_obj.scheduled_at else 'draft'
            campaign_obj.total_recipients = len(campaign_obj.get_recipient_list())
            campaign_obj.save()
            messages.success(request, f'Campaign "{campaign_obj.name}" saved as {campaign_obj.status}.')
            return redirect('campaigns:campaign_list')
    # GET request or form initialization: display campaign form
    else:
        form = CampaignForm(user=request.user, instance=campaign)

    # Render campaign form template
    return render(request, 'campaigns/create.html', {
        'form': form,
        'senders': senders,
        'campaign': campaign,
        'contact_lists': ContactList.objects.filter(user=request.user),
        'available_tags': ContactTag.objects.filter(user=request.user),
    })


@login_required
def campaign_create(request):
    """Create a new campaign.
    
    Args:
        request: The HTTP request object.
    
    Returns:
        HttpResponse: Rendered campaign form template.
    """
    return _campaign_form_view(request)


@login_required
def campaign_edit(request, campaign_id):
    """Edit an existing campaign.
    
    Args:
        request: The HTTP request object.
        campaign_id (int): Primary key of the campaign to edit.
    
    Returns:
        HttpResponse: Rendered campaign form template for editing.
    """
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    return _campaign_form_view(request, campaign=campaign)


@login_required
def campaign_view(request, campaign_id):
    """View a campaign in read-only mode.
    
    Args:
        request: The HTTP request object.
        campaign_id (int): Primary key of the campaign to view.
    
    Returns:
        HttpResponse: Rendered campaign form with all fields disabled.
    """
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    return _campaign_form_view(request, campaign=campaign, read_only=True)


@login_required
def campaign_send(request, campaign_id):
    """Send a draft campaign or resend an existing campaign.
    
    Handles POST requests to send a campaign. Accumulates sent counts if re-sending
    the same campaign multiple times.
    
    Args:
        request: The HTTP request object with POST method.
        campaign_id (int): Primary key of the campaign to send.
    
    Returns:
        HttpResponseRedirect: Redirect to campaign list after send attempt.
    """
    # Validate POST method
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    if request.method != 'POST':
        return redirect('campaigns:campaign_list')

    pre_send_errors, recipient_count = _validate_campaign_ready_to_send(campaign)
    if pre_send_errors:
        for error in pre_send_errors:
            messages.error(request, error)
        return redirect('campaigns:campaign_edit', campaign_id=campaign.id)

    # Mark campaign as sending and save
    campaign.status = 'sending'
    campaign.total_recipients = recipient_count
    campaign.save(update_fields=['status', 'total_recipients', 'updated_at'])
    try:
        # Build tracking base URL for open/click tracking
        base_url = (settings.TRACKING_BASE_URL or request.build_absolute_uri('/')).rstrip('/')
        sent_count, failed_count, last_error = send_campaign_with_smtp(campaign, base_url)
        # Accumulate values for re-sends
        campaign.sent_count = (campaign.sent_count or 0) + sent_count
        campaign.bounce_count = (campaign.bounce_count or 0) + failed_count
        campaign.status = 'sent' if campaign.sent_count > 0 else 'failed'
        campaign.save(update_fields=['sent_count', 'bounce_count', 'status', 'updated_at'])

        if failed_count > 0:
            messages.warning(
                request,
                f'Campaign sent with partial failures. Sent: {sent_count}, failed: {failed_count}. '
                f'{last_error or ""}'.strip(),
            )
        else:
            messages.success(request, f'Campaign "{campaign.name}" sent successfully to {sent_count} recipients.')
    except Exception as exc:
        campaign.status = 'failed'
        campaign.save(update_fields=['status', 'updated_at'])
        messages.error(request, f'Campaign send failed: {exc}')

    return redirect('campaigns:campaign_list')


@login_required
def campaign_retry_failed(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    if request.method != 'POST':
        return redirect('campaigns:campaign_list')

    all_recipients = campaign.get_recipient_list()
    if not all_recipients:
        messages.error(request, 'No recipients found for this campaign.')
        return redirect('campaigns:campaign_edit', campaign_id=campaign.id)

    sent_recipients = set(
        campaign.engagements.values_list('recipient_email', flat=True)
    )
    retry_recipients = [email for email in all_recipients if email not in sent_recipients]

    if not retry_recipients:
        messages.info(request, 'No failed recipients left to retry.')
        return redirect('campaigns:campaign_list')

    campaign.status = 'sending'
    campaign.save(update_fields=['status', 'updated_at'])
    try:
        base_url = (settings.TRACKING_BASE_URL or request.build_absolute_uri('/')).rstrip('/')
        sent_count, failed_count, last_error = send_campaign_with_smtp(
            campaign,
            base_url,
            recipients_override=retry_recipients,
        )
        campaign.sent_count = (campaign.sent_count or 0) + sent_count
        campaign.bounce_count = (campaign.bounce_count or 0) + failed_count
        campaign.status = 'sent' if campaign.sent_count > 0 else 'failed'
        campaign.save(update_fields=['sent_count', 'bounce_count', 'status', 'updated_at'])

        if failed_count > 0:
            messages.warning(
                request,
                f'Retry completed with partial failures. Sent: {sent_count}, failed: {failed_count}. '
                f'{last_error or ""}'.strip(),
            )
        else:
            messages.success(request, f'Retry successful. Sent to {sent_count} previously failed recipients.')
    except Exception as exc:
        campaign.status = 'failed'
        campaign.save(update_fields=['status', 'updated_at'])
        messages.error(request, f'Retry failed: {exc}')

    return redirect('campaigns:campaign_list')


@login_required
def campaign_delete(request, campaign_id):
    """Delete a campaign.
    
    Only processes POST requests. Redirects GET requests to campaign list.
    
    Args:
        request: The HTTP request object with POST method.
        campaign_id (int): Primary key of the campaign to delete.
    
    Returns:
        HttpResponseRedirect: Redirect to campaign list after deletion.
    """
    # Validate ownership and method
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    if request.method != 'POST':
        return redirect('campaigns:campaign_list')

    # Delete and redirect
    campaign_name = campaign.name
    campaign.delete()
    messages.success(request, f'Campaign "{campaign_name}" deleted successfully.')
    return redirect('campaigns:campaign_list')


@login_required
def campaign_list(request):
    """Display a paginated list of campaigns with engagement summaries.
    
    Shows campaign status breakdown counts and email statistics (sent, opened, clicked)
    aggregated from EmailEngagement records.
    
    Args:
        request: The HTTP request object containing the authenticated user.
    
    Returns:
        HttpResponse: Rendered campaigns list template with campaign and stats data.
    """
    # Fetch campaigns and engagement data for current user only
    campaigns_qs = Campaign.objects.filter(user=request.user).select_related('sender')
    engagements = EmailEngagement.objects.filter(campaign__user=request.user)

    query = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or 'all').strip().lower()
    start_date = (request.GET.get('start') or '').strip()
    end_date = (request.GET.get('end') or '').strip()

    if query:
        campaigns_qs = campaigns_qs.filter(Q(name__icontains=query) | Q(subject__icontains=query))

    valid_statuses = {choice[0] for choice in Campaign.STATUS_CHOICES}
    if status in valid_statuses:
        campaigns_qs = campaigns_qs.filter(status=status)
    else:
        status = 'all'

    if start_date:
        campaigns_qs = campaigns_qs.filter(updated_at__date__gte=start_date)
    if end_date:
        campaigns_qs = campaigns_qs.filter(updated_at__date__lte=end_date)

    paginator = Paginator(campaigns_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    campaigns = page_obj.object_list
    # Count campaigns by status for display filters/summary
    status_counts = {
        'all': Campaign.objects.filter(user=request.user).count(),
        'draft': Campaign.objects.filter(user=request.user, status='draft').count(),
        'scheduled': Campaign.objects.filter(user=request.user, status='scheduled').count(),
        'sent': Campaign.objects.filter(user=request.user, status='sent').count(),
        'failed': Campaign.objects.filter(user=request.user, status='failed').count(),
    }
    # Aggregate email metrics from EmailEngagement (event-driven, not denormalized fields)
    email_totals = {
        'recipients': campaigns.aggregate(Sum('total_recipients'))['total_recipients__sum'] or 0,
        'sent': engagements.count(),
        'opened': engagements.filter(opened_at__isnull=False).count(),  # Unique opens
        'clicked': engagements.filter(clicked_at__isnull=False).count(),  # Unique clicks
    }
    return render(request, 'campaigns/list.html', {
        'campaigns': campaigns,
        'page_obj': page_obj,
        'status_counts': status_counts,
        'email_totals': email_totals,
        'filters': {
            'q': query,
            'status': status,
            'start': start_date,
            'end': end_date,
        },
    })


@login_required
def campaign_duplicate(request, campaign_id):
    source_campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)

    duplicate = Campaign.objects.create(
        user=request.user,
        sender=source_campaign.sender,
        name=f"{source_campaign.name} (Copy)",
        subject=source_campaign.subject,
        body_html=source_campaign.body_html,
        body_text=source_campaign.body_text,
        recipient_emails=source_campaign.recipient_emails,
        from_name=source_campaign.from_name,
        reply_to=source_campaign.reply_to,
        status='draft',
        scheduled_at=None,
        total_recipients=source_campaign.total_recipients,
        spam_score=source_campaign.spam_score,
        spam_risk=source_campaign.spam_risk,
    )

    messages.success(request, f'Campaign duplicated as "{duplicate.name}".')
    return redirect('campaigns:campaign_edit', campaign_id=duplicate.id)


@login_required
def campaign_analytics(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)

    opened_engagements = campaign.engagements.filter(opened_at__isnull=False).order_by('-opened_at', 'recipient_email')
    top_clicked_links = (
        campaign.click_events
        .values('clicked_url')
        .annotate(total_clicks=Count('id'))
        .order_by('-total_clicks', 'clicked_url')[:10]
    )

    now = timezone.now()
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    start_hour = current_hour - timedelta(hours=23)

    hourly_opens_raw = (
        campaign.engagements
        .filter(opened_at__gte=start_hour, opened_at__lte=now)
        .annotate(hour=TruncHour('opened_at'))
        .values('hour')
        .annotate(total_opens=Count('id'))
        .order_by('hour')
    )
    opens_by_hour = {item['hour']: item['total_opens'] for item in hourly_opens_raw if item['hour'] is not None}

    timeline = []
    max_opens = 1
    for index in range(24):
        hour_point = start_hour + timedelta(hours=index)
        open_count = opens_by_hour.get(hour_point, 0)
        max_opens = max(max_opens, open_count)
        timeline.append({
            'hour_label': timezone.localtime(hour_point).strftime('%H:%M'),
            'opens': open_count,
        })

    for point in timeline:
        point['height_pct'] = round((point['opens'] / max_opens) * 100) if max_opens else 0

    context = {
        'campaign': campaign,
        'opened_engagements': opened_engagements,
        'top_clicked_links': top_clicked_links,
        'timeline': timeline,
    }
    return render(request, 'campaigns/analytics.html', context)


@login_required
def campaign_analytics_export_csv(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    export_type = (request.GET.get('type') or 'opens').strip().lower()

    if export_type == 'links':
        rows = (
            campaign.click_events
            .values('clicked_url')
            .annotate(total_clicks=Count('id'))
            .order_by('-total_clicks', 'clicked_url')
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="campaign_{campaign.id}_clicked_links.csv"'
        writer = csv.writer(response)
        writer.writerow(['campaign_id', 'campaign_name', 'clicked_url', 'total_clicks'])
        for row in rows:
            writer.writerow([
                campaign.id,
                campaign.name,
                row['clicked_url'],
                row['total_clicks'],
            ])
        return response

    engagements = campaign.engagements.order_by('-opened_at', 'recipient_email')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="campaign_{campaign.id}_opens.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'campaign_id',
        'campaign_name',
        'recipient_email',
        'sent_at',
        'opened_at',
        'clicked_at',
        'open_count',
        'click_count',
    ])
    for engagement in engagements:
        writer.writerow([
            campaign.id,
            campaign.name,
            engagement.recipient_email,
            engagement.sent_at.isoformat() if engagement.sent_at else '',
            engagement.opened_at.isoformat() if engagement.opened_at else '',
            engagement.clicked_at.isoformat() if engagement.clicked_at else '',
            engagement.open_count,
            engagement.click_count,
        ])
    return response


def campaign_track_open(request, token):
    """Track email opens via tracking pixel.
    
    Called when the 1x1 transparent GIF pixel is loaded in the recipient's email client.
    Records the first open timestamp and increments open counter. Updates campaign's
    unique_open_count if this is the recipient's first open.
    
    Note: Open tracking only works if emails are sent from a public domain. Localhost
    tracking URLs cannot be reached by external email clients, so opens remain untracked
    in development environments.
    
    Args:
        request: The HTTP request object from the tracking pixel load.
        token (str): The unique tracking token for the recipient's email engagement.
    
    Returns:
        HttpResponse: 1x1 transparent GIF pixel with no-cache headers to prevent proxy caching.
    """
    # Fetch engagement record by tracking token
    tracking = EmailEngagement.objects.filter(tracking_token=token).select_related('campaign').first()
    if tracking:
        now = timezone.now()
        # Detect first open to set opened_at timestamp
        first_open = tracking.opened_at is None
        tracking.open_count = (tracking.open_count or 0) + 1  # Increment open counter
        tracking.last_event_at = now  # Record activity timestamp
        if first_open:
            tracking.opened_at = now  # Set first open time
        tracking.save(update_fields=['open_count', 'last_event_at', 'opened_at'])

        # Update campaign's unique open count if this is first open for recipient
        if first_open:
            update_campaign_unique_open_count(tracking.campaign)

    # Return 1x1 transparent GIF pixel with no-cache to prevent CDN serving stale data
    pixel_bytes = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==')
    response = HttpResponse(pixel_bytes, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def campaign_track_click(request, token):
    """Track email link clicks and redirect to destination.
    
    Called when recipient clicks a tracked link in the email. Records click event
    and redirects to the intended URL. If click is first open, also marks email
    as opened and updates campaign unique_open_count.
    
    Args:
        request: The HTTP request object with 'next' parameter containing target URL.
        token (str): The unique tracking token for the recipient's email engagement.
    
    Returns:
        HttpResponseRedirect: Redirect to the original destination URL, or home if invalid.
    """
    # Extract and validate destination URL from query parameter
    next_url = unquote_plus(request.GET.get('next', '')).strip()
    parsed = urlparse(next_url)
    is_valid_redirect = bool(next_url and parsed.scheme in ('http', 'https') and parsed.netloc)

    # Fetch engagement record by tracking token
    tracking = EmailEngagement.objects.filter(tracking_token=token).select_related('campaign').first()
    if tracking:
        now = timezone.now()
        # Detect first click to set clicked_at timestamp
        first_click = tracking.clicked_at is None
        # Check if this click is also the first time opening the email
        first_open_via_click = tracking.opened_at is None
        tracking.click_count = (tracking.click_count or 0) + 1  # Increment click counter
        tracking.last_event_at = now  # Record activity timestamp
        if first_click:
            tracking.clicked_at = now  # Set first click time
        if first_open_via_click:
            tracking.opened_at = now  # Set first open time (click implies open)
        tracking.save(update_fields=['click_count', 'last_event_at', 'clicked_at', 'opened_at'])

        # Update campaign's unique open count if this is first open via click
        if first_open_via_click:
            update_campaign_unique_open_count(tracking.campaign)

        if is_valid_redirect:
            EmailClickEvent.objects.create(
                campaign=tracking.campaign,
                engagement=tracking,
                clicked_url=next_url,
            )

    # Only redirect to valid http/https URLs with proper domain (prevent open-redirect attacks)
    if is_valid_redirect:
        return HttpResponseRedirect(next_url)
    # Invalid URL: redirect to home page
    return redirect('home')


