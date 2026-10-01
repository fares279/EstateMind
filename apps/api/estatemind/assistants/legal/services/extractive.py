"""Answers without a language model: quote the most relevant sentences of the retrieved
official texts, with their citations.

Used when no LLM endpoint is reachable (the page used to answer only "the answer-writing
service is unreachable"). Every sentence shown is copied verbatim from a retrieved passage,
so the answer is grounded by construction; it is labelled as a quotation.
"""
from __future__ import annotations

import math
import re

MAX_SENTENCES = 4
MIN_SIMILARITY = 0.35          # below this a sentence is not about the question
RELATIVE_TO_BEST = 0.75        # and it must be close to the best sentence
MIN_WORDS = 6

INTRO = {
    'en': "Here is what the official texts say on this point (quoted directly, in their original language):",
    'fr': "Voici ce que disent les textes officiels sur ce point (citations directes) :",
    'ar': "إليك ما تنص عليه النصوص الرسمية في هذه المسألة (اقتباس حرفي):",
}
OUTRO = {
    'en': "These are quotations, not legal advice; a notary or lawyer can apply them to your situation.",
    'fr': "Ce sont des citations, pas un avis juridique ; un notaire ou un avocat peut les appliquer à votre cas.",
    'ar': "هذه اقتباسات وليست استشارة قانونية؛ يمكن لموثق أو محامٍ تطبيقها على وضعك.",
}

_SPLIT = re.compile(r'(?<=[.;:!?؟])\s+(?=[A-ZÀ-ÖØ-Þ؀-ۿ«"(\d])')


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(' '.join(text.split())) if len(s.split()) >= MIN_WORDS]


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def select(question: str, passages, embed) -> list[tuple[int, str, float]]:
    """(passage rank starting at 1, sentence, similarity) for the most relevant sentences,
    in the order they appear in the sources. `embed(texts) -> vectors`."""
    candidates = [(rank, s) for rank, p in enumerate(passages, start=1) for s in _sentences(p.text)]
    if not candidates:
        return []
    vectors = embed([question] + [s for _, s in candidates])
    q, rest = vectors[0], vectors[1:]
    scored = [(rank, s, _cosine(q, v)) for (rank, s), v in zip(candidates, rest)]
    best = max(sim for *_, sim in scored)
    keep = [x for x in scored if x[2] >= MIN_SIMILARITY and x[2] >= best * RELATIVE_TO_BEST]
    keep = sorted(keep, key=lambda x: -x[2])[:MAX_SENTENCES]
    order = {id(x): i for i, x in enumerate(scored)}
    return sorted(keep, key=lambda x: order[id(x)])


def compose(selected: list[tuple[int, str, float]], language: str) -> str:
    quotes = '\n\n'.join(f'«{sentence}» [{rank}]' for rank, sentence, _ in selected)
    return f"{INTRO.get(language, INTRO['en'])}\n\n{quotes}\n\n{OUTRO.get(language, OUTRO['en'])}"
