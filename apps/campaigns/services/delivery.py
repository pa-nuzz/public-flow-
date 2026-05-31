import smtplib
import ssl
import re
import random
from urllib.parse import quote_plus
from uuid import uuid4

from django.core.mail import EmailMultiAlternatives
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.models import EmailEngagement

from .content import text_to_html, sanitize_html


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
    # Sanitize HTML before adding tracking
    sanitized = sanitize_html(html_body)
    with_links = _inject_link_tracking(sanitized, tracking_token, base_url)
    return _inject_open_pixel(with_links, tracking_token, base_url)


def update_campaign_unique_open_count(campaign) -> None:
    unique_opens = campaign.engagements.filter(opened_at__isnull=False).aggregate(count=Count('id'))['count'] or 0
    campaign.open_count = unique_opens
    campaign.save(update_fields=['open_count', 'updated_at'])


def send_campaign_with_smtp(campaign, base_url: str, recipients_override=None):
    from django.db import models
    sender = campaign.sender
    if not sender:
        raise ValueError('Select a sender profile before sending.')

    recipients = recipients_override if recipients_override is not None else campaign.get_recipient_list()
    recipients = [email.strip().lower() for email in recipients if email and email.strip()]
    if not recipients:
        raise ValueError('Add at least one recipient email before sending.')

    # Reset daily quota if it's a new day
    sender.reset_daily_quota_if_needed()
    available_quota = max(sender.daily_limit - sender.emails_sent_today, 0)
    if available_quota == 0:
        raise ValueError('Sender daily limit reached. Increase limit or wait until next reset.')

    # Build job list containing content to send to each recipient
    jobs = [] # list of tuples: (recipient, subject, plain_body, html_body, variant_obj)

    if campaign.is_ab_test:
        variants = list(campaign.variants.all().order_by('label'))
        if len(variants) < 2:
            raise ValueError('A/B test campaigns must have at least 2 variants created.')

        var_a = variants[0]
        var_b = variants[1]

        if campaign.ab_test_status == 'pending':
            # Run the A/B test: split target lists into random variants
            total_count = len(recipients)
            count_a = max(1, int(total_count * var_a.percentage / 100))
            count_b = max(1, int(total_count * var_b.percentage / 100))

            random.shuffle(recipients)
            recips_a = recipients[:count_a]
            recips_b = recipients[count_a:count_a + count_b]

            for r in recips_a:
                jobs.append((r, var_a.subject, var_a.body_text, var_a.body_html, var_a))
            for r in recips_b:
                jobs.append((r, var_b.subject, var_b.body_text, var_b.body_html, var_b))

            campaign.ab_test_status = 'running'
            campaign.save(update_fields=['ab_test_status', 'updated_at'])

            # Dispatch background task for winner evaluation
            try:
                from apps.campaigns.tasks import evaluate_ab_test_winner
                evaluate_ab_test_winner.apply_async((campaign.id,), countdown=campaign.ab_test_duration_hours * 3600)
            except Exception as e:
                # Celery or Redis might not be running; will fallback to manual evaluation in UI
                pass

        elif campaign.ab_test_status == 'running':
            raise ValueError(
                'A/B test is currently running. Please wait for the test to complete '
                'or end the test manually in the analytics dashboard to deliver the winner.'
            )

        elif campaign.ab_test_status == 'completed':
            winner = campaign.winner_variant or var_a
            
            # Exclude already contacted recipients
            sent_emails = set(campaign.engagements.values_list('recipient_email', flat=True))
            remaining = [r for r in recipients if r not in sent_emails]

            for r in remaining:
                jobs.append((r, winner.subject, winner.body_text, winner.body_html, winner))
    else:
        # Standard campaign logic
        plain_body = campaign.body_text.strip() if campaign.body_text else ''
        html_body = campaign.body_html.strip() if campaign.body_html else ''
        if not html_body and plain_body:
            html_body = text_to_html(plain_body)
        if not plain_body and html_body:
            plain_body = 'This email contains HTML content. Please use an HTML-compatible mail client.'

        for r in recipients:
            jobs.append((r, campaign.subject, plain_body, html_body, None))

    # Restrict to available quota
    jobs = jobs[:available_quota]
    if not jobs:
        return 0, 0, "No unsent recipients within quota limits."

    smtp_password = sender.get_password()
    if not smtp_password:
        raise ValueError('Could not decrypt SMTP password for this sender. Re-save sender credentials.')

    from_name = (campaign.from_name or sender.display_name or '').strip()
    from_header = f'{from_name} <{sender.from_email}>' if from_name else sender.from_email
    reply_to = campaign.reply_to or sender.from_email

    sent_count = 0
    failed_count = len(recipients) - len(jobs)
    last_error = None

    for recipient, subject, p_body, h_body, variant_obj in jobs:
        tracking_token = uuid4().hex
        tracked_html_body = _build_tracked_html(h_body, tracking_token, base_url)
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
                    subject=subject,
                    body=p_body,
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
                    campaign_variant=variant_obj,
                    recipient_email=recipient,
                    tracking_token=tracking_token,
                )

                if variant_obj:
                    variant_obj.sent_count = models.F('sent_count') + 1
                    variant_obj.save(update_fields=['sent_count'])

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
            continue

    sender.emails_sent_today += sent_count
    sender.last_reset_date = timezone.now().date()
    sender.save(update_fields=['emails_sent_today', 'last_reset_date'])

    return sent_count, failed_count, last_error



def send_test_email_with_smtp(campaign, test_email: str):
    sender = campaign.sender
    if not sender:
        raise ValueError('Select a sender profile before sending a test email.')

    recipient = (test_email or '').strip().lower()
    if not recipient:
        raise ValueError('Provide a test email address.')

    smtp_password = sender.get_password()
    if not smtp_password:
        raise ValueError('Could not decrypt SMTP password for this sender. Re-save sender credentials.')

    plain_body = campaign.body_text.strip() if campaign.body_text else ''
    html_body = campaign.body_html.strip() if campaign.body_html else ''
    if not html_body and plain_body:
        html_body = text_to_html(plain_body)
    if not plain_body and html_body:
        plain_body = 'This email contains HTML content. Please use an HTML-compatible mail client.'

    if not plain_body and not html_body:
        raise ValueError('Message content is required before sending a test email.')

    from_name = (campaign.from_name or sender.display_name or '').strip()
    from_header = f'{from_name} <{sender.from_email}>' if from_name else sender.from_email
    reply_to = campaign.reply_to or sender.from_email

    # Reset daily quota if it's a new day
    sender.reset_daily_quota_if_needed()
    available_quota = max(sender.daily_limit - sender.emails_sent_today, 0)
    if available_quota == 0:
        raise ValueError('Sender daily limit reached. Increase limit or wait until next reset.')

    subject = campaign.subject or 'Test Campaign'

    if sender.smtp_port == 465:
        smtp_client = smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, timeout=20)
    else:
        smtp_client = smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=20)

    with smtp_client as server:
        if sender.smtp_port != 465 and sender.use_tls:
            server.starttls(context=ssl.create_default_context())
        server.login(sender.username, smtp_password)

        message = EmailMultiAlternatives(
            subject=f'[TEST] {subject}',
            body=plain_body,
            from_email=from_header,
            to=[recipient],
            reply_to=[reply_to] if reply_to else None,
        )
        if html_body:
            message.attach_alternative(html_body, 'text/html')
        server.sendmail(from_header, [recipient], message.message().as_string())

    sender.emails_sent_today += 1
    sender.last_reset_date = timezone.now().date()
    sender.save(update_fields=['emails_sent_today', 'last_reset_date'])
