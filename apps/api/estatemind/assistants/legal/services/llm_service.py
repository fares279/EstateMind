"""
LLM client for an OpenAI-compatible /chat/completions endpoint (Token Factory
by default; Ollama, vLLM and others expose the same API).
"""
import logging
import time

import requests
import urllib3

logger = logging.getLogger(__name__)


_MODEL_FALLBACKS = (
    'hosted_vllm/Llama-3.1-70B-Instruct',
    'hosted_vllm/Llama-3.1-8B-Instruct',
    'meta-llama/Meta-Llama-3.1-8B-Instruct',
    'mistralai/Mistral-7B-Instruct-v0.3',
)

_AVAILABILITY_TTL = 60  # seconds
_availability_cache: dict = {}


class LLMUnavailable(RuntimeError):
    """The endpoint could not be reached (network, DNS, timeout)."""


def _cfg() -> dict:
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def _verify():
    # Token Factory serves a self-signed certificate. LLM_VERIFY_SSL may be
    # True/False or a path to a CA bundle that trusts it.
    verify = _cfg().get('LLM_VERIFY_SSL', False)
    if verify is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return verify


def model_name() -> str:
    return _cfg().get('LLM_MODEL', 'hosted_vllm/Llama-3.1-70B-Instruct')


def chat(messages: list[dict], max_tokens: int = 750, temperature: float = 0.1) -> str:
    """Send a chat conversation; returns the assistant's text."""
    cfg = _cfg()
    base = cfg.get('LLM_API_URL', 'https://tokenfactory.esprit.tn/api').rstrip('/')
    url = f"{base}/chat/completions"
    headers = {'Authorization': f"Bearer {cfg.get('LLM_API_KEY', '')}", 'Content-Type': 'application/json'}
    candidates = list(dict.fromkeys(m for m in (model_name(), *_MODEL_FALLBACKS) if m))
    payload_base = {'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens, 'top_p': 0.9}
    timeout = cfg.get('LLM_TIMEOUT', 90)

    last_error: str | None = None
    for model in candidates:
        try:
            resp = requests.post(url, json={**payload_base, 'model': model}, headers=headers,
                                 timeout=timeout, verify=_verify())
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
            _availability_cache['value'] = (True, time.monotonic())
            return content.strip()
        except requests.exceptions.Timeout:
            raise LLMUnavailable("The AI service took too long to respond. Please try again.")
        except requests.exceptions.HTTPError as exc:
            status_code = getattr(exc.response, 'status_code', None)
            body = (getattr(exc.response, 'text', '') or '')[:200]
            last_error = f"AI service HTTP error {status_code}: {body}"
            if status_code == 404 and 'model' in body.lower():
                logger.warning("Legal LLM model not found: %s", model)
                continue
            raise RuntimeError(last_error)
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"Unexpected response from AI service: {exc}")
        except requests.exceptions.RequestException as exc:
            _availability_cache['value'] = (False, time.monotonic())
            raise LLMUnavailable(f"Could not reach the AI service: {exc}")

    raise RuntimeError(last_error or "AI service model not available.")


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 750) -> str:
    return chat([{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
                max_tokens=max_tokens)


def check_availability(force: bool = False) -> bool:
    """True when the endpoint answered recently (any HTTP status below 500).

    Unreachable hosts (DNS failure, refused connection, timeout) are reported
    as unavailable; results are cached for a minute.
    """
    cached = _availability_cache.get('value')
    if cached and not force and time.monotonic() - cached[1] < _AVAILABILITY_TTL:
        return cached[0]

    cfg = _cfg()
    available = False
    if cfg.get('LLM_API_KEY'):
        base = cfg.get('LLM_API_URL', 'https://tokenfactory.esprit.tn/api').rstrip('/')
        headers = {'Authorization': f"Bearer {cfg['LLM_API_KEY']}"}
        for path in ('/models', '/v1/models'):
            try:
                resp = requests.get(f"{base}{path}", headers=headers, timeout=5, verify=_verify())
                if resp.status_code < 500:
                    available = True
                    break
            except requests.exceptions.RequestException:
                continue
    _availability_cache['value'] = (available, time.monotonic())
    return available
