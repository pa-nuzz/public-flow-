"""Intelligence app views for spam analysis.

Provides API endpoints for analyzing email content and calculating spam risk scores.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
import json
import logging

from .services import analyze_spam_text

logger = logging.getLogger(__name__)


@login_required
@csrf_protect
@require_POST
def analyze_spam(request):
    """Analyze email text for spam indicators via AJAX.
    
    Accepts POST request with email content and returns spam score (0-100)
    and risk level (Very Low, Low, Medium, High).
    
    Args:
        request: HTTP request with JSON body containing 'text' or 'content' field.
    
    Returns:
        JsonResponse: JSON with success status, spam_score, and risk_level.
    """
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
