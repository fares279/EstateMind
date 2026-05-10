"""
LLM service using Token Factory (OpenAI-compatible API).
Calls /chat/completions with a Bearer token — no local Ollama needed.
"""
import requests
import logging
import urllib3

# Token Factory uses a self-signed cert; suppress the noise
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


_MODEL_FALLBACKS = (
    'hosted_vllm/Llama-3.1-70B-Instruct',
    'hosted_vllm/Llama-3.1-8B-Instruct',
    'meta-llama/Meta-Llama-3.1-8B-Instruct',
    'mistralai/Mistral-7B-Instruct-v0.3',
)


def _cfg() -> dict:
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 750) -> str:
    cfg = _cfg()
    base = cfg.get('LLM_API_URL', 'https://tokenfactory.esprit.tn/api').rstrip('/')
    url = f"{base}/chat/completions"
    api_key = cfg.get('LLM_API_KEY', '')
    configured_model = cfg.get('LLM_MODEL', 'hosted_vllm/Llama-3.1-70B-Instruct')
    model_candidates = [configured_model, *_MODEL_FALLBACKS]
    # Keep order stable while removing duplicates.
    model_candidates = list(dict.fromkeys(m for m in model_candidates if m))

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload_base = {
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_prompt},
        ],
        'temperature': 0.2,
        'max_tokens': max_tokens,
        'top_p': 0.9,
        'frequency_penalty': 0.0,
        'presence_penalty': 0.0,
    }

    last_error: str | None = None
    for model in model_candidates:
        payload = dict(payload_base)
        payload['model'] = model
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90, verify=False)
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content']
            return content.strip()
        except requests.exceptions.Timeout:
            raise RuntimeError("The AI service took too long to respond. Please try again.")
        except requests.exceptions.HTTPError as exc:
            status_code = getattr(exc.response, 'status_code', None)
            body = (getattr(exc.response, 'text', '') or '')[:200]
            message = f"AI service HTTP error {status_code}: {body}"
            last_error = message
            if status_code == 404 and 'model' in body.lower():
                logger.warning("Legal LLM model not found: %s", model)
                continue
            raise RuntimeError(message)
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"Unexpected response from AI service: {exc}")
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Could not reach the AI service: {exc}")

    if last_error:
        raise RuntimeError(last_error)
    raise RuntimeError("AI service model not available.")


def check_availability() -> bool:
    """
    Verify Token Factory API is reachable.
    Returns False only when definitively offline (no API key, or connection refused).
    Timeouts are treated as "available" because the server may be campus-only and
    slow to respond from off-network, but functional when reached.
    """
    cfg = _cfg()
    api_key = cfg.get('LLM_API_KEY', '')
    if not api_key:
        return False
    base = cfg.get('LLM_API_URL', 'https://tokenfactory.esprit.tn/api').rstrip('/')
    headers = {'Authorization': f'Bearer {api_key}'}
    for path in ['/models', '/v1/models', '']:
        try:
            resp = requests.get(f"{base}{path}", headers=headers, timeout=5, verify=False)
            if resp.status_code < 500:
                return True
        except requests.exceptions.Timeout:
            # Timeout ≠ offline — treat as available (campus server may be slow off-network)
            return True
        except requests.exceptions.ConnectionError:
            # Connection refused or DNS failure — definitive offline signal
            continue
        except Exception:
            continue
    return True  # Give benefit of the doubt if no definitive failure
