import html
import smtplib
import ssl
import re
import base64
from urllib.parse import quote_plus, unquote_plus, urlparse
from uuid import uuid4

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import Count
from apps.senders.models import Sender
from .models import Campaign, EmailEngagement
from .forms import CampaignForm
from django.contrib import messages

def _text_to_html(text):
    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines()]
    blocks = [f"<p>{html.escape(line)}</p>" for line in lines if line]
    return '\n'.join(blocks)


def _inject_link_tracking(html_body, tracking_token, base_url):
    if not html_body:
        return ''

    click_base = f"{base_url}{reverse('campaigns:track_click', kwargs={'token': tracking_token})}"

    def _replace_href(match):
        quote_char = match.group(1)
        original_url = (match.group(2) or '').strip()
        if not original_url.startswith(('http://', 'https://')):
            return match.group(0)
        tracked = f"{click_base}?next={quote_plus(original_url)}"
        return f"href={quote_char}{tracked}{quote_char}"

    pattern = re.compile(r'href\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)
    return pattern.sub(_replace_href, html_body)


def _inject_open_pixel(html_body, tracking_token, base_url):
    open_url = f"{base_url}{reverse('campaigns:track_open', kwargs={'token': tracking_token})}"
    pixel = f'<img src="{open_url}" width="1" height="1" alt="" style="display:block;opacity:0;max-height:0;max-width:0;" />'
    return f"{html_body}\n{pixel}" if html_body else pixel


def _build_tracked_html(html_body, tracking_token, base_url):
    with_links = _inject_link_tracking(html_body, tracking_token, base_url)
    return _inject_open_pixel(with_links, tracking_token, base_url)


def _update_campaign_unique_open_count(campaign):
    unique_opens = campaign.engagements.filter(opened_at__isnull=False).aggregate(count=Count('id'))['count'] or 0
    campaign.open_count = unique_opens
    campaign.save(update_fields=['open_count', 'updated_at'])


def _send_campaign_with_smtp(campaign, base_url):
    sender = campaign.sender
    if not sender:
        raise ValueError('Select a sender profile before sending.')

    recipients = campaign.get_recipient_list()
    if not recipients:
        raise ValueError('Add at least one recipient email before sending.')

    smtp_password = sender.get_password()
    if not smtp_password:
        raise ValueError('Could not decrypt SMTP password for this sender. Re-save sender credentials.')

    plain_body = campaign.body_text.strip() if campaign.body_text else ''
    html_body = campaign.body_html.strip() if campaign.body_html else ''
    if not html_body and plain_body:
        html_body = _text_to_html(plain_body)
    if not plain_body and html_body:
        plain_body = 'This email contains HTML content. Please use an HTML-compatible mail client.'

    from_name = (campaign.from_name or sender.display_name or '').strip()
    from_header = f'{from_name} <{sender.from_email}>' if from_name else sender.from_email
    reply_to = campaign.reply_to or sender.from_email
    available_quota = max(sender.daily_limit - sender.emails_sent_today, 0)
    if available_quota == 0:
        raise ValueError('Sender daily limit reached. Increase limit or wait until next reset.')

    target_recipients = recipients[:available_quota]
    blocked_recipients = max(len(recipients) - len(target_recipients), 0)

    if sender.smtp_port == 465:
        smtp_client = smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, timeout=20)
    else:
        smtp_client = smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=20)

    sent_count = 0
    failed_count = blocked_recipients
    last_error = None

    with smtp_client as server:
        if sender.smtp_port != 465 and sender.use_tls:
            server.starttls(context=ssl.create_default_context())
        server.login(sender.username, smtp_password)

        for recipient in target_recipients:
            tracking_token = uuid4().hex
            tracked_html_body = _build_tracked_html(html_body, tracking_token, base_url)
            try:
                message = EmailMultiAlternatives(
                    subject=campaign.subject,
                    body=plain_body,
                    from_email=from_header,
                    to=[recipient],
                    reply_to=[reply_to] if reply_to else None,
                )
                if tracked_html_body:
                    message.attach_alternative(tracked_html_body, 'text/html')
                server.sendmail(from_header, [recipient], message.message().as_string())
                sent_count += 1
                EmailEngagement.objects.create(
                    campaign=campaign,
                    recipient_email=recipient,
                    tracking_token=tracking_token,
                )
            except smtplib.SMTPAuthenticationError:
                raise ValueError(
                    "Gmail authentication failed. You must use an App Password, not your regular "
                    "Gmail password. Generate one at: https://myaccount.google.com/apppasswords"
                )
            except smtplib.SMTPRecipientsRefused as exc:
                failed_count += 1
                last_error = f"Recipient refused: {exc}"
            except Exception as exc:
                failed_count += 1
                last_error = str(exc)

    sender.emails_sent_today += sent_count
    sender.last_reset_date = timezone.now().date()
    sender.save(update_fields=['emails_sent_today', 'last_reset_date'])

    return sent_count, failed_count, last_error


def _campaign_form_view(request, campaign=None):
    senders = Sender.objects.filter(user=request.user, is_active=True)

    if request.method == 'POST':
        form = CampaignForm(request.POST, user=request.user, instance=campaign)
        action = request.POST.get('action', 'save_draft')

        if form.is_valid():
            campaign_obj = form.save(commit=False)
            campaign_obj.user = request.user
            campaign_obj.body_html = _text_to_html(campaign_obj.body_text or '')

            if action == 'send_now':
                campaign_obj.status = 'sending'
                campaign_obj.total_recipients = len(campaign_obj.get_recipient_list())
                campaign_obj.save()
                try:
                    base_url = request.build_absolute_uri('/').rstrip('/')
                    sent_count, failed_count, last_error = _send_campaign_with_smtp(campaign_obj, base_url)
                    campaign_obj.sent_count = sent_count
                    campaign_obj.bounce_count = failed_count
                    campaign_obj.status = 'sent' if sent_count > 0 else 'failed'
                    campaign_obj.save(update_fields=['sent_count', 'bounce_count', 'status', 'updated_at'])

                    if failed_count > 0:
                        messages.warning(
                            request,
                            f'Campaign sent with partial failures. Sent: {sent_count}, failed: {failed_count}. '
                            f'{last_error or ""}'.strip(),
                        )
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

    return render(
        request,
        'campaigns/create.html',
        {
            'form': form,
            'senders': senders,
            'campaign': campaign,
        },
    )


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
        sent_count, failed_count, last_error = _send_campaign_with_smtp(campaign, base_url)
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
            _update_campaign_unique_open_count(tracking.campaign)

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