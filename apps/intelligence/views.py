from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
import json, os, hashlib, logging
from .services import analyze_spam_text

logger = logging.getLogger(__name__)

def verify_model_integrity(path, expected_hash_env_var):
    expected = os.environ.get(expected_hash_env_var, '')
    if not expected:
        logger.warning(f"No hash configured for {path} — skipping integrity check")
        return True
    with open(path, 'rb') as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    return actual == expected

@login_required
@csrf_protect
@require_POST
def analyze_spam(request):
    try:
        data = json.loads(request.body)
        text = data.get('text') or data.get('content') or ''
        result = analyze_spam_text(text)
        
        return JsonResponse({
            'success': True,
            **result,
        })
    except Exception as e:
        logger.error(f"Spam analysis error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'An error occurred during analysis.'}, status=400)
