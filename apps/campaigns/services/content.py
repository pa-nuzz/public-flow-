import html

from apps.intelligence.ml_model import predict_spam_score


def text_to_html(text: str) -> str:
    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines()]
    blocks = [f"<p>{html.escape(line)}</p>" for line in lines if line]
    return '\n'.join(blocks)


def apply_campaign_spam_signals(campaign_obj) -> None:
    content = f"{campaign_obj.subject} {campaign_obj.body_text}"
    try:
        score = predict_spam_score(content)
        campaign_obj.spam_score = score
        if score >= 75:
            campaign_obj.spam_risk = 'high'
        elif score >= 45:
            campaign_obj.spam_risk = 'medium'
        else:
            campaign_obj.spam_risk = 'low'
    except Exception:
        pass


def merge_recipient_emails(existing_recipient_emails: str, list_emails: list[str]) -> str:
    existing = [email.strip() for email in (existing_recipient_emails or '').split(',') if email.strip()]
    merged = list(dict.fromkeys(existing + list_emails))
    return ', '.join(merged)
