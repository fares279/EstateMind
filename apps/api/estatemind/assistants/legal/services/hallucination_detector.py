"""Sentence-level grounding check for legal answers, used as a gate.

Each answer sentence is checked with an NLI model against every retrieved
passage separately (premise = passage, hypothesis = sentence) and keeps its
best entailment probability. The multilingual model handles French passages
with English or Arabic answers.

decide() turns the result into what the engine does with the answer:
  PASS       enough sentences are supported: return the answer
  FLAG       mostly supported: return it with unsupported sentences marked
  FAIL       not supported: regenerate once, then refuse
Disclaimers (e.g. "consult a notary") and statements that the sources do not
cover a point carry no legal claim and are not checked.
"""
import logging
import re
import threading

logger = logging.getLogger(__name__)

PASS, FLAG, FAIL = 'pass', 'flag', 'fail'

_EXEMPT = re.compile(
    r"notaire|notary|avocat|lawyer|attorney|professionnel|professional advice|consult|"
    r"ne (?:précise|mentionne|couvre|traite) pas|do(?:es)? not (?:specify|mention|cover|address|contain)|"
    r"not (?:covered|specified|mentioned) in|sources? (?:provided|available)|"
    r"موثق|محامي|عدل منفذ|لا تتضمن|لا تذكر",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\s*\[(?:\d+(?:\s*,\s*\d+)*)\]")


class HallucinationDetector:
    SENTENCE_THRESHOLD = 0.50   # entailment probability for a sentence to count as supported
    PASS_RATIO = 0.80           # share of checked sentences that must be supported to PASS
    FLAG_RATIO = 0.50           # below this the answer FAILs

    _pipe = None
    _lock = threading.Lock()

    def __init__(self, model_name: str | None = None):
        from django.conf import settings
        self.model_name = model_name or getattr(settings, 'LEGAL_RAG', {}).get(
            'NLI_MODEL', 'MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli')
        self._nli_available = self._load()

    def _load(self) -> bool:
        if HallucinationDetector._pipe is not None:
            return True
        with HallucinationDetector._lock:
            if HallucinationDetector._pipe is None:
                try:
                    from transformers import pipeline
                    HallucinationDetector._pipe = pipeline(
                        'text-classification', model=self.model_name, device=-1, top_k=None)
                    logger.info("NLI model loaded: %s", self.model_name)
                except Exception as exc:  # noqa: BLE001
                    logger.error("NLI model %s unavailable (%s); grounding falls back to word overlap",
                                 self.model_name, exc)
                    return False
        return True

    # ── scoring ──────────────────────────────────────────────────────────────
    def _entailment_scores(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        if not self._nli_available:
            return [self._overlap(p, h) for p, h in pairs]
        outputs = HallucinationDetector._pipe(
            [{'text': p, 'text_pair': h} for p, h in pairs], truncation=True, max_length=512, batch_size=16)
        scores = []
        for out in outputs:
            labels = {d['label'].lower(): d['score'] for d in out}
            scores.append(float(labels.get('entailment', 0.0)))
        return scores

    @staticmethod
    def _overlap(premise: str, hypothesis: str) -> float:
        p, h = set(premise.lower().split()), set(hypothesis.lower().split())
        return len(p & h) / len(h) if h else 0.0

    def check_answer(self, answer_text: str, retrieved_passages: list[str]) -> dict:
        sentences = self._split_sentences(answer_text)
        checked, exempt = [], []
        for s in sentences:
            claim = _CITATION.sub('', s).strip()
            if len(claim) < 15 or _EXEMPT.search(claim):
                exempt.append(s)
            else:
                checked.append((s, claim))

        pairs = [(p, claim) for _, claim in checked for p in retrieved_passages]
        flat = self._entailment_scores(pairs)
        n = max(len(retrieved_passages), 1)
        results = []
        for i, (sentence, _) in enumerate(checked):
            per_passage = flat[i * n:(i + 1) * n] if retrieved_passages else [0.0]
            best = max(per_passage) if per_passage else 0.0
            results.append({
                'sentence': sentence,
                'entailment_score': round(best, 3),
                'supporting_passage': int(per_passage.index(best)) + 1 if retrieved_passages else None,
                'grounded': best >= self.SENTENCE_THRESHOLD,
                'display_text': self._apply_hedging(sentence, best),
            })

        grounded = [r for r in results if r['grounded']]
        ratio = len(grounded) / len(results) if results else (1.0 if exempt else 0.0)
        avg = sum(r['entailment_score'] for r in results) / len(results) if results else ratio
        return {
            'sentences': results,
            'exempt_sentences': exempt,
            'grounded_ratio': round(ratio, 3),
            'average_score': round(avg, 3),
            'grounded_count': len(grounded),
            'total_sentences': len(results),
            'ungrounded_sentences': [r['sentence'] for r in results if not r['grounded']],
            'method': 'nli' if self._nli_available else 'word_overlap',
            'decision': self.decide(ratio, len(results)),
        }

    def decide(self, grounded_ratio: float, checked: int) -> str:
        if checked == 0:
            return PASS
        if grounded_ratio >= self.PASS_RATIO:
            return PASS
        if grounded_ratio >= self.FLAG_RATIO:
            return FLAG
        return FAIL

    def _apply_hedging(self, sentence: str, score: float) -> str:
        if score >= self.SENTENCE_THRESHOLD:
            return sentence
        if score >= 0.25:
            return f"[Note: the following may need verification] {sentence}"
        return f"[Unverified against retrieved sources: {sentence}]"

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
        parts = re.split(r'(?<=[.!?؟])\s+|\n+', text)
        return [s.strip() for s in parts if s.strip()]
