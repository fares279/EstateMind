"""Scores legal answers on the chatbot's four quality dimensions.

Weights and labels match chatbot.ResponseQualityMonitor so the two assistants'
scores are comparable:
  overall = relevance*0.35 + groundedness*0.40 + length*0.15 + attribution*0.10
  GOOD >= 0.85, ACCEPTABLE >= 0.70, POOR below.

Legal-specific measures: relevance is multilingual embedding similarity
between question and answer (answers are often in a different language from
the French sources, so word overlap under-counts); groundedness is the NLI
grounded-sentence ratio; attribution is the share of checked sentences that
carry a valid [n] citation.
"""
import re

_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class LegalResponseQualityMonitor:
    MIN_SENTENCES = 1
    MAX_SENTENCES = 8
    MAX_WORDS = 250

    def __init__(self):
        from estatemind.assistants.shared_models import INTENT_MODEL, get_sentence_model
        self.model = get_sentence_model(INTENT_MODEL)

    def relevance(self, question: str, answer: str) -> float:
        from sentence_transformers import util
        emb = self.model.encode([question, answer], convert_to_tensor=True, normalize_embeddings=True)
        sim = float(util.cos_sim(emb[0], emb[1]))
        # Relevant answers score ~0.5-0.8 with this encoder; map 0.2..0.7 onto 0..1.
        return max(0.0, min(1.0, (sim - 0.2) / 0.5))

    @staticmethod
    def citation_score(grounding: dict, n_passages: int) -> float:
        checked = grounding.get('sentences', [])
        if not checked:
            return 1.0 if grounding.get('exempt_sentences') else 0.0
        valid = 0
        for s in checked:
            refs = [int(x) for m in _CITE.findall(s['sentence']) for x in m.split(',')]
            if refs and all(1 <= r <= n_passages for r in refs):
                valid += 1
        return valid / len(checked)

    def evaluate(self, question: str, answer: str, grounding: dict, n_passages: int) -> dict:
        relevance = self.relevance(question, answer)
        groundedness = float(grounding.get('grounded_ratio', 0.0))
        sentences = len(grounding.get('sentences', [])) + len(grounding.get('exempt_sentences', []))
        length_ok = self.MIN_SENTENCES <= sentences <= self.MAX_SENTENCES and len(answer.split()) <= self.MAX_WORDS
        citations = self.citation_score(grounding, n_passages)
        overall = (
            relevance * 0.35
            + groundedness * 0.40
            + (1.0 if length_ok else 0.5) * 0.15
            + (0.7 + 0.3 * citations) * 0.10
        )
        return {
            'relevance': round(relevance, 3),
            'groundedness': round(groundedness, 3),
            'citation_score': round(citations, 3),
            'length_appropriate': length_ok,
            'overall': round(overall, 3),
            'quality_label': 'GOOD' if overall >= 0.85 else 'ACCEPTABLE' if overall >= 0.70 else 'POOR',
        }
