"""Hand-labelled chatbot intents (data/chatbot_intents.json) and accuracy on them."""

from __future__ import annotations

import json
from functools import lru_cache

from config.paths import DATA_DIR

INTENTS_FILE = DATA_DIR / 'chatbot_intents.json'


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(INTENTS_FILE.read_text(encoding='utf-8'))


def examples() -> dict[str, list[str]]:
    return load()['examples']


def evaluation_set() -> list[dict]:
    return load()['evaluation']


def evaluate(classify, rows: list[dict] | None = None) -> dict:
    """Accuracy of `classify(text) -> intent` against the held-out labels.

    The labels are independent of the classifier. (evaluate_intent_accuracy used
    to re-classify logged queries and compare with the intent the same classifier
    had logged, so it measured consistency, not accuracy.)"""
    rows = evaluation_set() if rows is None else rows
    by_intent: dict[str, dict] = {}
    confusion: dict[str, int] = {}
    correct = 0
    for row in rows:
        predicted = classify(row['text'])
        hit = predicted == row['intent']
        correct += hit
        stats = by_intent.setdefault(row['intent'], {'correct': 0, 'total': 0})
        stats['total'] += 1
        stats['correct'] += hit
        key = f"{row['intent']}->{predicted}"
        confusion[key] = confusion.get(key, 0) + 1
    return {
        'total': len(rows), 'correct': correct,
        'accuracy': correct / len(rows) if rows else 0.0,
        'accuracy_by_intent': {k: v['correct'] / v['total'] for k, v in by_intent.items()},
        'confusion': confusion,
    }
