import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

def generate_ai_copy(prompt: str, tone: str = "professional") -> dict:
    """
    Generate email subject and body copy based on a user prompt and tone configuration.
    Utilizes the Gemini API via standard HTTP requests and forces JSON schema response format.

    Args:
        prompt (str): The user's instructions for the email copy.
        tone (str): The desired tone (e.g. 'casual', 'urgent', 'professional', 'creative').

    Returns:
        dict: A dictionary with 'subject' and 'body' keys, or default values on error.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        # Check settings or environment as fallback
        import os
        api_key = os.environ.get('GEMINI_API_KEY')

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured. Returning mock values.")
        return {
            "subject": f"[Mock - Key Missing] Subject in {tone} tone",
            "body": f"This is a mock email body generated for: '{prompt}'. To enable real generation, set your GEMINI_API_KEY in the .env file."
        }

    # Construct instructions based on tone
    tone_descriptions = {
        "professional": "polished, clear, and business-focused",
        "urgent": "action-oriented, time-sensitive, and compelling",
        "casual": "friendly, conversational, and lighthearted",
        "creative": "highly engaging, story-driven, and unique"
    }
    tone_desc = tone_descriptions.get(tone.lower(), "professional")

    system_instruction = (
        f"You are an expert marketing email copywriter. Write a highly converting marketing email "
        f"based on the instructions. The email tone must be {tone_desc}. "
        f"Do not include placeholders like '[First Name]' or similar tags unless explicitly requested; "
        f"instead write generic natural copy that reads well."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Instructions: {prompt}"}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "subject": {
                        "type": "STRING",
                        "description": "Engaging email subject line. Keep under 60 characters."
                    },
                    "body": {
                        "type": "STRING",
                        "description": "Clear and persuasive plain text email body copy."
                    }
                },
                "required": ["subject", "body"]
            }
        }
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=25.0)
        response.raise_for_status()
        result_json = response.json()
        
        # Parse the structured output out of the response
        candidates = result_json.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                import json
                structured_data = json.loads(parts[0].get("text", "{}"))
                return {
                    "subject": structured_data.get("subject", "").strip(),
                    "body": structured_data.get("body", "").strip()
                }
    except Exception as e:
        logger.error(f"Gemini API request failed: {e}")

    # Fallback default responses
    return {
        "subject": "Error generating copy",
        "body": "Could not connect to Gemini API. Please check your credentials or network and try again."
    }
