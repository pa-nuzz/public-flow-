import base64
from urllib.parse import unquote_plus, urlparse

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse, HttpResponseRedirect
from apps.senders.models import Sender
from .models import Campaign, EmailEngagement
from .forms import CampaignForm
from django.contrib import messages
from apps.contacts.models import ContactList
from .services import (
    text_to_html,
    apply_campaign_spam_signals,
    merge_recipient_emails,
    send_campaign_with_smtp,
    update_campaign_unique_open_count,
)


def _campaign_form_view(request, campaign=None):
    senders = Sender.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        form = CampaignForm(request.POST, user=request.user, instance=campaign)
        action = request.POST.get('action', 'save_draft')

        if form.is_valid():
            campaign_obj = form.save(commit=False)
            campaign_obj.user = request.user
            campaign_obj.body_html = text_to_html(campaign_obj.body_text or '')
            apply_campaign_spam_signals(campaign_obj)

            # Merge contact list emails into recipient_emails
            contact_list = form.cleaned_data.get('contact_list')
            if contact_list:
                list_emails = contact_list.get_email_list()
                campaign_obj.recipient_emails = merge_recipient_emails(campaign_obj.recipient_emails, list_emails)

            if action == 'send_now':
                campaign_obj.status = 'sending'
                campaign_obj.total_recipients = len(campaign_obj.get_recipient_list())
                campaign_obj.save()
                try:
                    base_url = request.build_absolute_uri('/').rstrip('/')
                    sent_count, failed_count, last_error = send_campaign_with_smtp(campaign_obj, base_url)
                    campaign_obj.sent_count = sent_count
                    campaign_obj.bounce_count = failed_count
                    campaign_obj.status = 'sent' if sent_count > 0 else 'failed'
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

            campaign_obj.status = 'scheduled' if campaign_obj.scheduled_at else 'draft'
            campaign_obj.total_recipients = len(campaign_obj.get_recipient_list())
            campaign_obj.save()
            messages.success(request, f'Campaign "{campaign_obj.name}" saved as {campaign_obj.status}.')
            return redirect('campaigns:campaign_list')
    else:
        form = CampaignForm(user=request.user, instance=campaign)

    return render(request, 'campaigns/create.html', {
        'form': form,
        'senders': senders,
        'campaign': campaign,
        'contact_lists': ContactList.objects.filter(user=request.user),
    })

@login_required
def campaign_create(request):
    return _campaign_form_view(request)


@login_required
def campaign_edit(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    return _campaign_form_view(request, campaign=campaign)


@login_required
def campaign_send(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    if request.method != 'POST':
        return redirect('campaigns:campaign_list')

    campaign.status = 'sending'
    campaign.total_recipients = len(campaign.get_recipient_list())
    campaign.save(update_fields=['status', 'total_recipients', 'updated_at'])
    try:
        base_url = request.build_absolute_uri('/').rstrip('/')
        sent_count, failed_count, last_error = send_campaign_with_smtp(campaign, base_url)
        campaign.sent_count = sent_count
        campaign.bounce_count = failed_count
        campaign.status = 'sent' if sent_count > 0 else 'failed'
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
def campaign_delete(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    if request.method != 'POST':
        return redirect('campaigns:campaign_list')

    campaign_name = campaign.name
    campaign.delete()
    messages.success(request, f'Campaign "{campaign_name}" deleted successfully.')
    return redirect('campaigns:campaign_list')


@login_required
def campaign_list(request):
    campaigns = Campaign.objects.filter(user=request.user).select_related('sender')
    status_counts = {
        'all': campaigns.count(),
        'draft': campaigns.filter(status='draft').count(),
        'scheduled': campaigns.filter(status='scheduled').count(),
        'sent': campaigns.filter(status='sent').count(),
        'failed': campaigns.filter(status='failed').count(),
    }
    return render(request, 'campaigns/list.html', {'campaigns': campaigns, 'status_counts': status_counts})


def campaign_track_open(request, token):
    tracking = EmailEngagement.objects.filter(tracking_token=token).select_related('campaign').first()
    if tracking:
        now = timezone.now()
        first_open = tracking.opened_at is None
        tracking.open_count = (tracking.open_count or 0) + 1
        tracking.last_event_at = now
        if first_open:
            tracking.opened_at = now
        tracking.save(update_fields=['open_count', 'last_event_at', 'opened_at'])

        if first_open:
            update_campaign_unique_open_count(tracking.campaign)

    pixel_bytes = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==')
    response = HttpResponse(pixel_bytes, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def campaign_track_click(request, token):
    tracking = EmailEngagement.objects.filter(tracking_token=token).select_related('campaign').first()
    if tracking:
        now = timezone.now()
        first_click = tracking.clicked_at is None
        tracking.click_count = (tracking.click_count or 0) + 1
        tracking.last_event_at = now
        if first_click:
            tracking.clicked_at = now
        tracking.save(update_fields=['click_count', 'last_event_at', 'clicked_at'])

    next_url = unquote_plus(request.GET.get('next', '')).strip()
    parsed = urlparse(next_url)
    if next_url and parsed.scheme in ('http', 'https') and parsed.netloc:
        return HttpResponseRedirect(next_url)
    return redirect('home')


