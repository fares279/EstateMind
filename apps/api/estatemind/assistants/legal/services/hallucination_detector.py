import re
from transformers import pipeline


class HallucinationDetector:
    SENTENCE_THRESHOLD = 0.70
    ALERT_THRESHOLD = 0.85

    def __init__(self):
        try:
            self._nli = pipeline('text-classification', model='cross-encoder/nli-deberta-v3-small', device=-1)
            self._nli_available = True
        except Exception as e:
            # Fallback if tokenizer cache is corrupted
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to initialize NLI model: {e}. Using fallback mode.")
            self._nli = None
            self._nli_available = False

    def check_answer(self, answer_text: str, retrieved_passages: list[str]) -> dict:
        sentences = self._split_sentences(answer_text)
        context = ' '.join(retrieved_passages[:3])

        sentence_results = []
        for sentence in sentences:
            if len(sentence.strip()) < 10:
                continue
            score = self._entailment_score(sentence, context)
            sentence_results.append({
                'sentence': sentence,
                'entailment_score': round(score, 3),
                'grounded': score >= self.SENTENCE_THRESHOLD,
                'display_text': self._apply_hedging(sentence, score),
            })

        if not sentence_results:
            return {'status': 'no_sentences', 'average_score': 0.0}

        avg_score = sum(r['entailment_score'] for r in sentence_results) / len(sentence_results)
        grounded_count = sum(r['grounded'] for r in sentence_results)

        return {
            'sentences': sentence_results,
            'average_score': round(avg_score, 3),
            'grounded_count': grounded_count,
            'total_sentences': len(sentence_results),
            'answer_grounded': avg_score >= self.ALERT_THRESHOLD,
            'needs_alert': avg_score < self.ALERT_THRESHOLD,
        }

    def _entailment_score(self, sentence: str, context: str) -> float:
        if not self._nli_available:
            # Fallback: use simple keyword overlap scoring
            context_words = set(context.lower().split())
            sentence_words = set(sentence.lower().split())
            if not context_words or not sentence_words:
                return 0.5
            overlap = len(context_words & sentence_words) / len(context_words | sentence_words)
            return min(0.95, overlap * 1.2)  # Cap at 0.95 to indicate uncertainty
        
        try:
            result = self._nli(f"{context} </s></s> {sentence}", truncation=True, max_length=512)
            for item in result:
                if item['label'] == 'ENTAILMENT':
                    return item['score']
            return 0.0
        except Exception:
            # Fallback to keyword overlap if inference fails
            context_words = set(context.lower().split())
            sentence_words = set(sentence.lower().split())
            if not context_words or not sentence_words:
                return 0.5
            overlap = len(context_words & sentence_words) / len(context_words | sentence_words)
            return min(0.95, overlap * 1.2)

    def _apply_hedging(self, sentence: str, score: float) -> str:
        if score >= self.SENTENCE_THRESHOLD:
            return sentence
        if score >= 0.40:
            return f"[Note: the following may need verification] {sentence}"
        return f"[Unverified against retrieved sources: {sentence}]"

    def _split_sentences(self, text: str) -> list[str]:
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
