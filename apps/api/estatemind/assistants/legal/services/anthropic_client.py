"""Claude backend for the legal assistant (official `anthropic` SDK).

Takes the same OpenAI-style message list the rest of the pipeline builds
(system first, then alternating user/assistant) and returns the answer text.
Selected with LEGAL_LLM_PROVIDER=anthropic (or the FALLBACK_ equivalent).
"""
import logging

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'claude-opus-5'
# Server-side refusal fallbacks ("default" routes by refusal category). Only
# models that accept the parameter get it.
_FALLBACK_MODELS = {'claude-opus-5', 'claude-fable-5-1'}
_FALLBACK_BETA = 'server-side-fallback-2026-07-01'


class ClaudeUnavailable(Exception):
    """Network failure, timeout, overload or 5xx after the SDK's own retries."""


class ClaudeRefused(Exception):
    """The request was declined (stop_reason 'refusal') by the whole fallback chain."""


def _client(cfg: dict) -> anthropic.Anthropic:
    kwargs = {'timeout': float(cfg.get('timeout', 90)), 'max_retries': 2}
    if cfg.get('api_key'):
        kwargs['api_key'] = cfg['api_key']  # else ANTHROPIC_API_KEY / `ant auth login` profile
    if cfg.get('base_url'):
        kwargs['base_url'] = cfg['base_url']
    return anthropic.Anthropic(**kwargs)


def chat(messages: list[dict], cfg: dict, max_tokens: int = 16000) -> str:
    model = cfg.get('model') or DEFAULT_MODEL
    system = '\n\n'.join(m['content'] for m in messages if m['role'] == 'system')
    turns = [{'role': m['role'], 'content': m['content']} for m in messages if m['role'] in ('user', 'assistant')]
    params = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=turns,
        output_config={'effort': cfg.get('effort') or 'medium'},
    )
    try:
        if model in _FALLBACK_MODELS and cfg.get('refusal_fallbacks', True):
            response = _client(cfg).beta.messages.create(betas=[_FALLBACK_BETA], fallbacks='default', **params)
        else:
            response = _client(cfg).messages.create(**params)
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
        raise ClaudeUnavailable(f'Could not reach Claude: {exc}') from exc
    except anthropic.RateLimitError as exc:
        raise ClaudeUnavailable(f'Claude rate limit reached: {exc.message}') from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise ClaudeUnavailable(f'Claude server error {exc.status_code}') from exc
        raise RuntimeError(f'Claude API error {exc.status_code}: {exc.message}') from exc

    if response.stop_reason == 'refusal':
        category = getattr(response.stop_details, 'category', None) if response.stop_details else None
        raise ClaudeRefused(f'Claude declined the request (category: {category})')
    return ''.join(block.text for block in response.content if block.type == 'text').strip()


def check_availability(cfg: dict) -> bool:
    try:
        _client({**cfg, 'timeout': 5}).models.retrieve(cfg.get('model') or DEFAULT_MODEL)
        return True
    except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.AuthenticationError,
            anthropic.PermissionDeniedError):
        return False
    except anthropic.APIStatusError as exc:
        return exc.status_code < 500
