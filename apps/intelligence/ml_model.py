import os
import pickle
import logging
import re
from django.conf import settings

MODEL_PATH = str(getattr(settings, 'ML_MODEL_PATH', os.path.join(settings.BASE_DIR, 'Data', 'spam_model.pkl')))
VECTORIZER_PATH = str(getattr(settings, 'ML_VECTORIZER_PATH', os.path.join(settings.BASE_DIR, 'Data', 'tfidf_vectorizer.pkl')))

_model = None
_vectorizer = None
logger = logging.getLogger(__name__)

SPAM_TRIGGER_WORDS = {
    'free', 'viagra', 'winner', 'guarantee', 'urgent', 'prize', 'claim',
    'bonus', 'offer', 'cash', 'money', 'click now', 'limited time'
}

HAM_GREETING_WORDS = {
    'hello', 'hi', 'hey', 'goodmorning', 'good', 'morning', 'afternoon',
    'evening', 'thanks', 'thank', 'regards', 'appreciate', 'interest'
}


def _tokenize(text):
    return re.findall(r"[a-zA-Z']+", (text or '').lower())


def _calibrate_spam_score(text, raw_score):
    tokens = _tokenize(text)
    token_set = set(tokens)
    token_count = len(tokens)

    has_spam_trigger = any(trigger in (text or '').lower() for trigger in SPAM_TRIGGER_WORDS)
    ham_hits = len(token_set & HAM_GREETING_WORDS)

    adjusted = float(raw_score)

    if token_count <= 6 and ham_hits >= 1 and not has_spam_trigger:
        adjusted = min(adjusted, 28.0)

    if token_count <= 10 and ham_hits >= 2 and not has_spam_trigger:
        adjusted = min(adjusted, 22.0)

    if has_spam_trigger:
        adjusted = max(adjusted, raw_score)

    return round(max(0.0, min(100.0, adjusted)), 1)


def _candidate_paths():
    base = str(settings.BASE_DIR)
    return [
        (MODEL_PATH, VECTORIZER_PATH),
        (os.path.join(base, 'ml_models', 'spam_model.pkl'), os.path.join(base, 'ml_models', 'tfidf_vectorizer.pkl')),
        (os.path.join(base, 'Data', 'spam_model.pkl'), os.path.join(base, 'Data', 'tfidf_vectorizer.pkl')),
        (os.path.join(base, 'notebooks', 'spam_model.pkl'), os.path.join(base, 'notebooks', 'tfidf_vectorizer.pkl')),
    ]

def get_model_and_vectorizer():
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        try:
            for model_path, vectorizer_path in _candidate_paths():
                if os.path.exists(model_path) and os.path.exists(vectorizer_path):
                    with open(model_path, 'rb') as f:
                        _model = pickle.load(f)
                    with open(vectorizer_path, 'rb') as f:
                        _vectorizer = pickle.load(f)
                    logger.info(f"Loaded ML model from {model_path} and vectorizer from {vectorizer_path}")
                    break
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            _model, _vectorizer = "heuristic", "heuristic"
    if _model is None or _vectorizer is None:
        _model, _vectorizer = "heuristic", "heuristic"
    return _model, _vectorizer

def predict_spam_score(text):
    """
    Predicts the spam score using the loaded TF-IDF vectorizer and scikit-learn model.
    Returns a score out of 100 representing the probability of being spam.
    """
    model, vectorizer = get_model_and_vectorizer()
    
    # If the model loaded successfully (is not the string "heuristic")
    if model != "heuristic" and vectorizer != "heuristic" and model is not None:
        try:
            # Transform text
            X = vectorizer.transform([text])
            # Predict probability - Assuming class 1 is Spam and class 0 is Ham
            # Return spam probability * 100 (0-100 scale where 100 = high spam risk)
            probs = model.predict_proba(X)[0]
            # probs[1] is the spam probability
            spam_prob = probs[1]
            spam_score = spam_prob * 100
            return _calibrate_spam_score(text, spam_score)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            
    # Fallback heuristic: start clean and raise with trigger density.
    text_lower = (text or '').lower()
    trigger_count = sum(1 for word in SPAM_TRIGGER_WORDS if word in text_lower)

    if trigger_count == 0:
        return _calibrate_spam_score(text, 10)
    if trigger_count == 1:
        return _calibrate_spam_score(text, 38)
    if trigger_count == 2:
        return _calibrate_spam_score(text, 62)
    return _calibrate_spam_score(text, 82)
