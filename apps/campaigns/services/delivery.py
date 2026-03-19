import smtplib
import ssl
import re
from urllib.parse import quote_plus
from uuid import uuid4

from django.core.mail import EmailMultiAlternatives
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.models import EmailEngagement

from .content import text_to_html


def _inject_link_tracking(html_body: str, tracking_token: str, base_url: str) -> str:
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


def _inject_open_pixel(html_body: str, tracking_token: str, base_url: str) -> str:
    open_url = f"{base_url}{reverse('campaigns:track_open', kwargs={'token': tracking_token})}"
    pixel = f'<img src="{open_url}" width="1" height="1" alt="" style="display:block;opacity:0;max-height:0;max-width:0;" />'
    return f"{html_body}\n{pixel}" if html_body else pixel


def _build_tracked_html(html_body: str, tracking_token: str, base_url: str) -> str:
    with_links = _inject_link_tracking(html_body, tracking_token, base_url)
    return _inject_open_pixel(with_links, tracking_token, base_url)


def update_campaign_unique_open_count(campaign) -> None:
    unique_opens = campaign.engagements.filter(opened_at__isnull=False).aggregate(count=Count('id'))['count'] or 0
    campaign.open_count = unique_opens
    campaign.save(update_fields=['open_count', 'updated_at'])


def send_campaign_with_smtp(campaign, base_url: str):
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
        html_body = text_to_html(plain_body)
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

    sent_count = 0
    failed_count = blocked_recipients
    last_error = None

    for recipient in target_recipients:
        tracking_token = uuid4().hex
        tracked_html_body = _build_tracked_html(html_body, tracking_token, base_url)
        try:
            if sender.smtp_port == 465:
                smtp_client = smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, timeout=20)
            else:
                smtp_client = smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=20)

            with smtp_client as server:
                if sender.smtp_port != 465 and sender.use_tls:
                    server.starttls(context=ssl.create_default_context())
                server.login(sender.username, smtp_password)

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
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPHeloError, smtplib.SMTPDataError, smtplib.SMTPException, OSError) as exc:
            failed_count += 1
            last_error = str(exc)
            continue
        except Exception as exc:
            failed_count += 1
            last_error = str(exc)
            continue

    sender.emails_sent_today += sent_count
    sender.last_reset_date = timezone.now().date()
    sender.save(update_fields=['emails_sent_today', 'last_reset_date'])

    return sent_count, failed_count, last_error
