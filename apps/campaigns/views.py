import html
import smtplib
import ssl

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from apps.senders.models import Sender
from .models import Campaign
from .forms import CampaignForm
from django.contrib import messages

def _text_to_html(text):
    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines()]
    blocks = [f"<p>{html.escape(line)}</p>" for line in lines if line]
    return '\n'.join(blocks)


def _send_campaign_with_smtp(campaign):
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
            try:
                message = EmailMultiAlternatives(
                    subject=campaign.subject,
                    body=plain_body,
                    from_email=from_header,
                    to=[recipient],
                    reply_to=[reply_to] if reply_to else None,
                )
                if html_body:
                    message.attach_alternative(html_body, 'text/html')
                server.sendmail(from_header, [recipient], message.message().as_string())
                sent_count += 1
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
                    sent_count, failed_count, last_error = _send_campaign_with_smtp(campaign_obj)
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
        sent_count, failed_count, last_error = _send_campaign_with_smtp(campaign)
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