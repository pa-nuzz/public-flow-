import logging

from apps.intelligence.ml_model import predict_spam_score

logger = logging.getLogger(__name__)


def get_risk_level(score: float) -> str:
    if score >= 75:
        return 'High'
    if score >= 45:
        return 'Medium'
    if score >= 20:
        return 'Low'
    return 'Very Low'


def analyze_spam_text(text: str) -> dict:
    score = predict_spam_score((text or '')[:10000])
    return {
        'spam_score': score,
        'risk_level': get_risk_level(score),
    }
