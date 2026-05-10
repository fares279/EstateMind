import requests
import logging

logger = logging.getLogger(__name__)


def _cfg():
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def _base_url() -> str:
    return _cfg().get('OLLAMA_URL', 'http://localhost:11434').rstrip('/')


def _model() -> str:
    return _cfg().get('OLLAMA_MODEL', 'llama3')


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 750) -> str:
    prompt = f"{system_prompt}\n\n{user_prompt}"
    payload = {
        'model': _model(),
        'prompt': prompt,
        'temperature': 0.2,
        'max_tokens': max_tokens,
        'stream': False,
    }

    base = _base_url()
    endpoints = ['/api/generate', '/api/completions', '/v1/completions']
    last_error = None

    for endpoint in endpoints:
        url = f"{base}{endpoint}"
        try:
            resp = requests.post(url, json=payload, timeout=90)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                if 'response' in data:
                    return str(data['response']).strip()
                if 'results' in data:
                    return str(data['results'][0].get('content', '')).strip()
                if 'choices' in data:
                    choice = data['choices'][0]
                    if isinstance(choice, dict) and 'message' in choice:
                        return str(choice['message'].get('content', '')).strip()
                    if isinstance(choice, dict) and 'text' in choice:
                        return str(choice['text']).strip()
            if isinstance(data, str):
                return data.strip()

        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning("Ollama endpoint %s failed: %s", url, exc)
            continue

    raise RuntimeError(
        f"Ollama unreachable on all endpoints. "
        f"Make sure Ollama is running (`ollama serve`) and the model is pulled "
        f"(`ollama pull {_model()}`). Last error: {last_error}"
    )


def check_availability() -> bool:
    try:
        resp = requests.get(f"{_base_url()}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
