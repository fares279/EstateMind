"""Per-endpoint rate limits. Rates live in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].

Each class counts per logged-in user, or per client IP when anonymous. Views
list these next to the default anon/user throttles (see with_defaults), so the
generous global limits still apply as well.
"""
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class _ScopeThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, 'user', None)
        ident = user.pk if user is not None and user.is_authenticated else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class LoginThrottle(_ScopeThrottle):
    scope = 'login'


class RegisterThrottle(_ScopeThrottle):
    scope = 'register'


class OTPThrottle(_ScopeThrottle):
    scope = 'otp'


class PasswordResetThrottle(_ScopeThrottle):
    scope = 'password_reset'


class ChatThrottle(_ScopeThrottle):
    scope = 'chat'


class LegalAskThrottle(_ScopeThrottle):
    scope = 'legal_ask'


class FeedbackThrottle(_ScopeThrottle):
    scope = 'feedback'


def with_defaults(*scoped):
    """Throttle list for a view: the global anon/user limits plus the given scopes."""
    return [AnonRateThrottle, UserRateThrottle, *scoped]
