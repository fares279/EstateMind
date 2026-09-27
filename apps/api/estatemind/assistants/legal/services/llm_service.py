"""
LLM access for the legal assistant.

Two endpoints, each configured from environment variables (see
.env.example): a primary one (Token Factory by default) and an optional
fallback that is used only when the primary is unreachable. Each endpoint is
either an OpenAI-compatible /chat/completions API (Token Factory, OpenAI,
Mistral, Groq, Together, vLLM, Ollama, Azure OpenAI...) or Claude, via the
official SDK (anthropic_client.py).
"""
import logging
import threading
import time

import requests
import urllib3

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE = 'openai_compatible'
ANTHROPIC = 'anthropic'

_MODEL_FALLBACKS = (  # tried in order on Token Factory when the configured model 404s
    'hosted_vllm/Llama-3.1-70B-Instruct',
    'hosted_vllm/Llama-3.1-8B-Instruct',
    'meta-llama/Meta-Llama-3.1-8B-Instruct',
    'mistralai/Mistral-7B-Instruct-v0.3',
)

_AVAILABILITY_TTL = 60  # seconds
_availability_cache: dict = {}
_last = threading.local()


class LLMUnavailable(RuntimeError):
    """No configured endpoint could be reached (network, DNS, timeout, overload)."""


def _cfg() -> dict:
    from django.conf import settings
    return getattr(settings, 'LEGAL_RAG', {})


def endpoints() -> list[dict]:
    """Configured endpoints in the order they are tried."""
    cfg = _cfg()
    primary = {
        'name': 'primary',
        'provider': cfg.get('LLM_PROVIDER', OPENAI_COMPATIBLE),
        'base_url': cfg.get('LLM_API_URL', 'https://tokenfactory.esprit.tn/api'),
        'api_key': cfg.get('LLM_API_KEY', ''),
        'model': cfg.get('LLM_MODEL', 'hosted_vllm/Llama-3.1-70B-Instruct'),
        'verify': cfg.get('LLM_VERIFY_SSL', False),
        'timeout': cfg.get('LLM_TIMEOUT', 90),
        'effort': cfg.get('LLM_EFFORT', 'medium'),
    }
    out = [primary]
    fb = cfg.get('LLM_FALLBACK') or {}
    if fb.get('provider') and (fb.get('model') or fb.get('provider') == ANTHROPIC):
        out.append({'name': 'fallback', 'verify': True, 'timeout': primary['timeout'],
                    'effort': primary['effort'], **{k: v for k, v in fb.items() if v not in (None, '')}})
    return out


def model_name() -> str:
    """Model that answered the most recent chat() in this thread (else the primary's)."""
    return getattr(_last, 'model', None) or endpoints()[0]['model']


def _verify(ep: dict):
    # Token Factory serves a self-signed certificate: verify may be True/False
    # or a path to a CA bundle that trusts it.
    if ep.get('verify') is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return ep.get('verify', True)


def _openai_chat(ep: dict, messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, str]:
    url = f"{ep['base_url'].rstrip('/')}/chat/completions"
    headers = {'Authorization': f"Bearer {ep.get('api_key', '')}", 'Content-Type': 'application/json'}
    candidates = [ep['model']]
    if ep['name'] == 'primary':
        candidates = list(dict.fromkeys([ep['model'], *_MODEL_FALLBACKS]))
    body = {'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens, 'top_p': 0.9}

    last_error = None
    for model in candidates:
        try:
            resp = requests.post(url, json={**body, 'model': model}, headers=headers,
                                 timeout=ep['timeout'], verify=_verify(ep))
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'].strip(), model
        except requests.exceptions.Timeout:
            raise LLMUnavailable(f"{ep['name']} LLM timed out")
        except requests.exceptions.HTTPError as exc:
            status_code = getattr(exc.response, 'status_code', None)
            text = (getattr(exc.response, 'text', '') or '')[:200]
            last_error = f"AI service HTTP error {status_code}: {text}"
            if status_code == 404 and 'model' in text.lower():
                logger.warning("Legal LLM model not found: %s", model)
                continue
            if status_code and (status_code >= 500 or status_code == 429):
                raise LLMUnavailable(last_error)
            raise RuntimeError(last_error)
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"Unexpected response from AI service: {exc}")
        except requests.exceptions.RequestException as exc:
            raise LLMUnavailable(f"Could not reach the {ep['name']} AI service: {exc}")
    raise RuntimeError(last_error or "AI service model not available.")


def _endpoint_chat(ep: dict, messages: list[dict], max_tokens: int, temperature: float) -> tuple[str, str]:
    if ep['provider'] == ANTHROPIC:
        from . import anthropic_client
        try:
            # Claude may think before answering; give it room beyond the answer length.
            return anthropic_client.chat(messages, ep, max_tokens=max(max_tokens, 16000)), \
                ep.get('model') or anthropic_client.DEFAULT_MODEL
        except anthropic_client.ClaudeUnavailable as exc:
            raise LLMUnavailable(str(exc)) from exc
        except anthropic_client.ClaudeRefused as exc:
            logger.warning('Legal LLM refusal: %s', exc)
            return '', ep.get('model') or anthropic_client.DEFAULT_MODEL
    return _openai_chat(ep, messages, max_tokens, temperature)


def chat(messages: list[dict], max_tokens: int = 750, temperature: float = 0.1) -> str:
    """Send a chat conversation; returns the assistant's text ('' if the model declined)."""
    failures = []
    for ep in endpoints():
        try:
            text, model = _endpoint_chat(ep, messages, max_tokens, temperature)
        except LLMUnavailable as exc:
            failures.append(str(exc))
            _availability_cache[ep['name']] = (False, time.monotonic())
            continue
        _last.model = model
        _availability_cache[ep['name']] = (True, time.monotonic())
        return text
    raise LLMUnavailable('; '.join(failures))


def generate(system_prompt: str, user_prompt: str, max_tokens: int = 750) -> str:
    return chat([{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
                max_tokens=max_tokens)


def _probe(ep: dict) -> bool:
    if ep['provider'] == ANTHROPIC:
        from . import anthropic_client
        return anthropic_client.check_availability(ep)
    if not ep.get('api_key'):
        return False
    headers = {'Authorization': f"Bearer {ep['api_key']}"}
    for path in ('/models', '/v1/models'):
        try:
            resp = requests.get(f"{ep['base_url'].rstrip('/')}{path}", headers=headers, timeout=5, verify=_verify(ep))
            if resp.status_code < 500:
                return True
        except requests.exceptions.RequestException:
            continue
    return False


def endpoint_status(force: bool = False) -> list[dict]:
    """Reachability of each configured endpoint (cached for a minute)."""
    out = []
    for ep in endpoints():
        cached = _availability_cache.get(ep['name'])
        if cached and not force and time.monotonic() - cached[1] < _AVAILABILITY_TTL:
            ok = cached[0]
        else:
            ok = _probe(ep)
            _availability_cache[ep['name']] = (ok, time.monotonic())
        out.append({'name': ep['name'], 'provider': ep['provider'], 'model': ep.get('model'), 'available': ok})
    return out


def check_availability(force: bool = False) -> bool:
    """True when at least one configured endpoint is reachable."""
    return any(e['available'] for e in endpoint_status(force))
