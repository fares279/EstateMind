"""Prompts and fixed user-facing messages for the legal assistant."""
import re

LANGUAGE_NAMES = {'en': 'English', 'fr': 'French', 'ar': 'Arabic'}

_ARABIC = re.compile(r'[؀-ۿ]')
_FRENCH = re.compile(
    r"[éèêàùçôîœ]|\b(le|la|les|des|du|une|est|sont|quel(?:le)?s?|comment|pour|dans|avec|peut|doit)\b",
    re.IGNORECASE)


def detect_language(text: str) -> str:
    if _ARABIC.search(text):
        return 'ar'
    if len(_FRENCH.findall(text)) >= 2:
        return 'fr'
    return 'en'


SYSTEM_PROMPT = """You are EstateMind's legal assistant for Tunisian law.

Answer ONLY from the numbered legal passages provided in the user's message.
Rules:
1. Every statement about the law must come from a passage and end with its citation, e.g. [1] or [2, 3].
2. If the passages do not answer the question, or only answer part of it, say plainly which part the available sources do not cover. Never fill gaps with outside knowledge, assumptions or typical practice.
3. Answer in {language}, even though the passages are in French.
4. Be concise: at most 6 sentences. Quote numbers, deadlines and rates exactly as the passage states them.
5. Do not give personalised legal advice. You may end by suggesting a notary or lawyer for the user's specific situation."""

STRICT_SUFFIX = """

Your previous answer contained statements that the passages do not support.
Write a new answer using only sentences that directly restate what a passage says, each with its citation. If the passages do not contain the answer, say so in one sentence."""


def build_messages(question: str, passages, language: str, history: list[dict] | None = None,
                   strict: bool = False) -> list[dict]:
    system = SYSTEM_PROMPT.format(language=LANGUAGE_NAMES.get(language, 'English'))
    if strict:
        system += STRICT_SUFFIX
    context = "\n\n".join(f"[{i}] ({p.label})\n{p.text}" for i, p in enumerate(passages, start=1))
    messages = [{'role': 'system', 'content': system}]
    for turn in (history or [])[-2:]:
        if turn.get('user') and turn.get('assistant'):
            messages.append({'role': 'user', 'content': turn['user']})
            messages.append({'role': 'assistant', 'content': turn['assistant']})
    messages.append({'role': 'user', 'content': f"Legal passages:\n\n{context}\n\nQuestion: {question}"})
    return messages


MESSAGES = {
    'greeting': {
        'en': "Hello! I answer questions about Tunisian property law, from the official legal texts I have "
              "indexed, and I cite the articles I rely on. For example:",
        'fr': "Bonjour ! Je réponds aux questions sur le droit immobilier tunisien, à partir des textes "
              "officiels que j'ai indexés, en citant les articles utilisés. Par exemple :",
        'ar': "مرحبا! أجيب عن الأسئلة المتعلقة بالقانون العقاري التونسي انطلاقا من النصوص الرسمية المفهرسة، "
              "مع ذكر الفصول التي أعتمد عليها. مثلا:",
    },
    'thanks': {
        'en': "You're welcome. Ask me another question about Tunisian property law whenever you like.",
        'fr': "Avec plaisir. Posez-moi une autre question sur le droit immobilier tunisien quand vous voulez.",
        'ar': "على الرحب والسعة. يمكنك طرح سؤال آخر عن القانون العقاري التونسي متى شئت.",
    },
    'out_of_scope': {
        'en': "I answer questions about Tunisian property law. For prices, valuations, forecasts or investment "
              "picks, please use the EstateMind advisor or the valuation tool.",
        'fr': "Je réponds aux questions sur le droit immobilier tunisien. Pour les prix, estimations, prévisions "
              "ou conseils d'investissement, utilisez l'assistant EstateMind ou l'outil d'estimation.",
        'ar': "أجيب عن الأسئلة المتعلقة بالقانون العقاري التونسي. بالنسبة للأسعار أو التقييم أو التوقعات أو "
              "فرص الاستثمار، يرجى استخدام مساعد EstateMind أو أداة التقييم.",
    },
    'no_sources': {
        'en': "The legal texts I have access to do not cover this question, so I can't answer it reliably. "
              "A notary or lawyer can advise you on this point.",
        'fr': "Les textes juridiques dont je dispose ne traitent pas de cette question ; je ne peux donc pas y "
              "répondre de façon fiable. Un notaire ou un avocat pourra vous renseigner.",
        'ar': "النصوص القانونية المتوفرة لدي لا تغطي هذا السؤال، لذلك لا يمكنني الإجابة عنه بشكل موثوق. "
              "يمكن لعدل إشهاد أو محامٍ إفادتك في هذه النقطة.",
    },
    'ungrounded': {
        'en': "I couldn't write an answer that is fully supported by the legal texts. The most relevant "
              "passages are listed below so you can read them directly.",
        'fr': "Je n'ai pas pu rédiger une réponse entièrement fondée sur les textes juridiques. Les passages "
              "les plus pertinents sont listés ci-dessous.",
        'ar': "لم أتمكن من صياغة إجابة مدعومة بالكامل بالنصوص القانونية. أهم المقاطع ذات الصلة مدرجة أدناه.",
    },
    'llm_unavailable': {
        'en': "The answer-writing service is unreachable right now. These are the most relevant legal "
              "passages for your question.",
        'fr': "Le service de rédaction des réponses est injoignable pour le moment. Voici les passages "
              "juridiques les plus pertinents pour votre question.",
        'ar': "خدمة صياغة الإجابات غير متاحة حالياً. هذه أهم المقاطع القانونية المتعلقة بسؤالك.",
    },
}


def message(kind: str, language: str) -> str:
    return MESSAGES[kind].get(language, MESSAGES[kind]['en'])
