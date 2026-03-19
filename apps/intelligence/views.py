from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
import json, os, hashlib, logging
from .ml_model import predict_spam_score

logger = logging.getLogger(__name__)

def verify_model_integrity(path, expected_hash_env_var):
    expected = os.environ.get(expected_hash_env_var, '')
    if not expected:
        logger.warning(f"No hash configured for {path} — skipping integrity check")
        return True
    with open(path, 'rb') as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    return actual == expected

def get_risk_level(score):
    # Score is spam probability * 100 (0-100 scale where 100 = max spam risk)
    if score >= 80:
        return 'High'
    elif score >= 55:
        return 'Medium'
    elif score >= 30:
        return 'Low'
    else:
        return 'Very Low'

@login_required
@csrf_protect
@require_POST
def analyze_spam(request):
    try:
        data = json.loads(request.body)
        text = (data.get('text') or data.get('content') or '')[:10000] # Input sanitization: truncate
        
        # In a real scenario, we'd check integrity before loading. 
        # Here we fix the logic as requested.
        score = predict_spam_score(text)
        
        return JsonResponse({
            'success': True,
            'spam_score': score,
            'risk_level': get_risk_level(score)
        })
    except Exception as e:
        logger.error(f"Spam analysis error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'An error occurred during analysis.'}, status=400)
