"""Retrieval quality of a legal collection, measured on data/eval_questions.json.

Answerable questions list what answers them: an article index of
clean_dataset_v2.json (int), or "<law name>:<article>" for an official text
(data/official), matched against the passage's article range. See gold_match. The legal
questions the corpus does not cover, and non-legal questions, measure whether
the retrieval gate (best similarity below RETRIEVAL_MIN_SIMILARITY) correctly
reports "no source".
"""
import json
import re
from pathlib import Path

EVAL_PATH = Path(__file__).resolve().parent.parent / 'data' / 'eval_questions.json'


def load_eval_questions() -> list[dict]:
    return json.loads(EVAL_PATH.read_text(encoding='utf-8'))['questions']


_REF_RANGE = re.compile(r'art\. (\d+)(?: (?:bis|ter|quater))?(?: à (\d+))?')


def gold_match(meta: dict, gold: list) -> bool:
    """Whether a retrieved passage is one of the gold sources."""
    for g in gold:
        if isinstance(g, int):
            if meta.get('article_index') == g:
                return True
            continue
        law, article = g.rsplit(':', 1)
        if meta.get('law_name') != law:
            continue
        m = _REF_RANGE.search(meta.get('article_ref', ''))
        if m and int(m.group(1)) <= int(article) <= int(m.group(2) or m.group(1)):
            return True
    return False


def source_label(meta: dict):
    """How a retrieved passage is reported in failures: index, or official reference."""
    return meta.get('article_index') if meta.get('article_index', -1) >= 0 else meta.get('article_ref')


class RetrievalQualityValidator:
    TARGET_RECALL = 0.90       # recall@5 over answerable questions
    TARGET_RECALL_AT_3 = 0.85
    K = 5

    def __init__(self, chroma_service, embedding_service, min_similarity: float | None = None):
        from django.conf import settings
        self.chroma = chroma_service
        self.embedder = embedding_service
        self.min_similarity = (min_similarity if min_similarity is not None
                               else getattr(settings, 'LEGAL_RAG', {}).get('RETRIEVAL_MIN_SIMILARITY', 0.52))

    def run_full_evaluation(self, collection_name: str) -> dict:
        hits = {1: 0, 3: 0, 5: 0}
        by_lang: dict[str, list[int]] = {}
        failures, gate = [], {'answerable_passed': 0, 'answerable': 0, 'negative_blocked': 0, 'negative': 0}

        for q in load_eval_questions():
            res = self.chroma.query(self.embedder.embed_text(q['question']), n_results=self.K,
                                    collection_name=collection_name)
            metas = res.get('metadatas', [[]])[0]
            dists = res.get('distances', [[]])[0]
            ranked = [source_label(m) for m in metas]
            top_sim = 1.0 - float(dists[0]) if dists else 0.0
            passes_gate = top_sim >= self.min_similarity

            if q['category'] == 'answerable':
                rank = next((i + 1 for i, m in enumerate(metas) if gold_match(m, q['gold'])), None)
                for k in hits:
                    hits[k] += bool(rank and rank <= k)
                stats = by_lang.setdefault(q['lang'], [0, 0])
                stats[0] += bool(rank and rank <= 3)
                stats[1] += 1
                gate['answerable'] += 1
                gate['answerable_passed'] += passes_gate
                if not rank or rank > 3:
                    failures.append({'id': q['id'], 'question': q['question'], 'gold': q['gold'],
                                     'retrieved_articles': ranked, 'top_similarity': round(top_sim, 3)})
            else:
                gate['negative'] += 1
                gate['negative_blocked'] += not passes_gate

        n = max(gate['answerable'], 1)
        recall = {k: hits[k] / n for k in hits}
        passed = recall[5] >= self.TARGET_RECALL and recall[3] >= self.TARGET_RECALL_AT_3
        return {
            'collection': collection_name,
            'recall_at_1': round(recall[1], 3),
            'recall_at_3': round(recall[3], 3),
            'recall_at_5': round(recall[5], 3),
            'recall_at_3_by_language': {k: f'{v[0]}/{v[1]}' for k, v in by_lang.items()},
            'gate_threshold': self.min_similarity,
            'gate_answerable_pass_rate': round(gate['answerable_passed'] / n, 3),
            'gate_negative_block_rate': round(gate['negative_blocked'] / max(gate['negative'], 1), 3),
            'target': self.TARGET_RECALL,
            'passed': passed,
            'total_questions': gate['answerable'],
            'found': hits[5],
            'missed': gate['answerable'] - hits[5],
            'failures': failures,
        }
