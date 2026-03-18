import os
import pickle
import logging
from django.conf import settings

MODEL_PATH = str(getattr(settings, 'ML_MODEL_PATH', os.path.join(settings.BASE_DIR, 'Data', 'spam_model.pkl')))
VECTORIZER_PATH = str(getattr(settings, 'ML_VECTORIZER_PATH', os.path.join(settings.BASE_DIR, 'Data', 'tfidf_vectorizer.pkl')))

_model = None
_vectorizer = None
logger = logging.getLogger(__name__)


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
            # We want to return the 'Safe Score', which is 100 - (Spam Probability * 100)
            # OR we can just return the Spam probability. 
            # Looking at the dashboard, "Spam Score 98/100" means 98% Safe usually.
            probs = model.predict_proba(X)[0]
            # Assuming probs[1] is spam probability
            spam_prob = probs[1]
            safe_score = (1.0 - spam_prob) * 100
            return round(safe_score, 1)
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            
    # Fallback heuristic
    spam_words = ['free', 'viagra', 'winner', 'guarantee', 'urgent']
    score = 100
    text_lower = text.lower()
    for word in spam_words:
        if word in text_lower:
            score -= 15
    return max(0, min(100, score))
