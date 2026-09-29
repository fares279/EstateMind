"""Personal facts a user states in a conversation (currently their name), shared by
the market chatbot and the legal assistant so both remember them the same way.
Stored in ConversationMemory.extracted_facts['user_name']."""
from __future__ import annotations

import re

_NAME = r"([A-Za-zÀ-ÿ؀-ۿ][A-Za-zÀ-ÿ؀-ۿ'\- ]{0,40})"
_INTRO_PATTERNS = [
    r'\bmy name is\s+' + _NAME,
    r'\bi am\s+' + _NAME,
    r'\bcall me\s+' + _NAME,
    r"\bje m'appelle\s+" + _NAME,
    r'\bmon nom est\s+' + _NAME,
    r'اسمي\s+' + _NAME,
]
_NAME_QUESTIONS = [
    'what is my name', "what's my name", 'do you know my name', 'remember my name', 'tell me my name',
    'what do you call me', "comment je m'appelle", 'quel est mon nom', 'tu connais mon nom', 'ما اسمي',
    'ما هو اسمي',
]
_REPLIES = {
    'known': {'en': 'Your name is {name}.', 'fr': 'Vous vous appelez {name}.', 'ar': 'اسمك {name}.'},
    'unknown': {'en': "I don’t know your name yet. You can tell me by saying 'my name is Bob'.",
                'fr': "Je ne connais pas encore votre nom. Dites-moi par exemple « je m'appelle Bob ».",
                'ar': 'لا أعرف اسمك بعد. يمكنك أن تقول مثلاً: اسمي بوب.'},
    'ack': {'en': "Nice to meet you, {name}. I'll remember that.", 'fr': 'Enchanté, {name}. Je m’en souviendrai.',
            'ar': 'تشرفت بمعرفتك يا {name}. سأتذكر ذلك.'},
}


def extract_user_name(message: str) -> str | None:
    """A self-introduced name ('my name is Bob', "je m'appelle Bob"), or None."""
    for pattern in _INTRO_PATTERNS:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            candidate = re.sub(r"[^A-Za-zÀ-ÿ؀-ۿ'\- ]+$", '', match.group(1).strip()).strip()
            if candidate:
                return candidate[:50]
    return None


def is_name_question(message: str) -> bool:
    lower = message.lower().strip()
    return any(phrase in lower for phrase in _NAME_QUESTIONS)


def name_response(name: str | None, language: str = 'en') -> str:
    kind = 'known' if name else 'unknown'
    return _REPLIES[kind].get(language, _REPLIES[kind]['en']).format(name=name)


def name_acknowledgement(name: str, language: str = 'en') -> str:
    return _REPLIES['ack'].get(language, _REPLIES['ack']['en']).format(name=name)
