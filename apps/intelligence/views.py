from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import json
from .ml_model import predict_spam_score

@csrf_protect
@require_POST
def analyze_spam(request):
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        score = predict_spam_score(text)
        
        return JsonResponse({
            'success': True,
            'spam_score': score,
            'risk_level': 'High' if score < 50 else 'Low' if score < 80 else 'Very Low'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
