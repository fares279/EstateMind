from transformers import pipeline

LEGAL_DOMAINS = {
    'transactions': ['buy', 'sell', 'purchase', 'registration', 'notary', 'deed', 'transfer', 'contract', 'signing', 'شراء', 'بيع'],
    'taxation': ['tax', 'capital gains', 'VAT', 'duties', 'fees', 'imposition', 'registration fees', 'ضريبة'],
    'zoning': ['zoning', 'land use', 'permit', 'construction', 'building', 'planning', 'urban', 'تصريح', 'بناء'],
    'inheritance': ['inheritance', 'heir', 'estate', 'succession', 'probate', 'death', 'deceased', 'إرث', 'ورث'],
    'foreign_ownership': ['foreign', 'non-resident', 'foreigner', 'nationality', 'non-Tunisian', 'investor', 'أجنبي', 'غير مقيم'],
}


class LegalDomainClassifier:
    def __init__(self):
        self._zero_shot = pipeline('zero-shot-classification', model='facebook/bart-large-mnli', device=-1)

    def classify(self, question: str) -> dict:
        q = question.lower()
        keyword_scores = {}
        for domain, keywords in LEGAL_DOMAINS.items():
            matches = 0
            for kw in keywords:
                if kw in q:
                    # Foreign ownership queries are often phrased with generic purchase verbs,
                    # so give explicit foreign markers a stronger weight than broad transaction terms.
                    matches += 2 if domain == 'foreign_ownership' else 1
            if matches > 0:
                keyword_scores[domain] = matches

        if keyword_scores:
            primary = max(keyword_scores, key=keyword_scores.get)
            secondary = [d for d, s in sorted(keyword_scores.items(), key=lambda x: -x[1]) if d != primary][:1]
            return {'primary_domain': primary, 'secondary_domains': secondary, 'method': 'keyword', 'confidence': min(0.95, keyword_scores[primary] * 0.3)}

        result = self._zero_shot(question, candidate_labels=list(LEGAL_DOMAINS.keys()))
        primary = result['labels'][0]
        confidence = result['scores'][0]
        secondary = result['labels'][1:2] if result['scores'][1] > 0.25 else []
        return {'primary_domain': primary, 'secondary_domains': secondary, 'method': 'zero_shot', 'confidence': round(confidence, 3)}
