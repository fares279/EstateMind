"""Legal question classification: is it a legal question, and which domain.

Same method as the chatbot's IntentClassifier — cosine similarity between the
question and short descriptions, using the shared multilingual encoder — plus
the legal keyword lists, which boost a domain when its terms appear.

Scope: the question is compared with descriptions of legal questions and of
the other things users ask EstateMind (prices, valuations, forecasts, where to
buy, small talk). Wrongly redirecting a legal question loses an answer, while
a non-legal question treated as legal is still stopped by the retrieval gate,
so a question is only redirected when it clearly matches a non-legal intent:
non-legal similarity >= NON_LEGAL_MIN and ahead of legal by SCOPE_MARGIN.
Thresholds were set on data/eval_questions.json.
"""
import logging
import re

logger = logging.getLogger(__name__)

LEGAL_DOMAINS = {
    'transactions': ['buy', 'sell', 'purchase', 'registration', 'notary', 'deed', 'transfer', 'contract', 'signing',
                     'acquisition', 'vente', 'achat', 'enregistrement', 'شراء', 'بيع', 'اقتناء'],
    'taxation': ['tax', 'capital gains', 'VAT', 'duties', 'fees', 'imposition', 'registration fees', 'impôt', 'TVA',
                 'droit fixe', 'ضريبة', 'أداء', 'معلوم'],
    'zoning': ['zoning', 'land use', 'permit', 'construction', 'building', 'planning', 'urban', 'permis', 'تصريح', 'بناء'],
    'inheritance': ['inheritance', 'heir', 'estate', 'succession', 'probate', 'death', 'deceased', 'héritier',
                    'إرث', 'ورث', 'ورثة'],
    'foreign_ownership': ['foreign', 'non-resident', 'foreigner', 'nationality', 'non-Tunisian', 'étranger',
                          'gouverneur', 'أجنبي', 'غير مقيم'],
    'debt_recovery': ['debt', 'creditor', 'debtor', 'mortgage', 'lien', 'assignment of receivables', 'créance',
                      'hypothèque', 'recouvrement', 'دين', 'رهن', 'إحالة'],
    'investment_funds': ['fund', 'units', 'securities', 'net asset value', 'redemption', 'fonds', 'OPCVM', 'parts',
                         'valeurs mobilières', 'صندوق'],
    'corporate': ['company', 'founders', 'shareholders', 'general meeting', 'société', 'fondateurs', 'assemblée',
                  'شركة', 'مؤسسين'],
    'leasing': ['lease', 'tenant', 'landlord', 'rent', 'bail', 'locataire', 'loyer', 'كراء', 'متسوغ'],
}

DOMAIN_DESCRIPTIONS = {
    'transactions': 'legal rules for buying, selling or registering real estate, contracts and deeds',
    'taxation': 'taxes, registration duties, VAT and fees under Tunisian tax law',
    'zoning': 'building permits, land use and urban planning regulations',
    'inheritance': 'inheritance of property and division between heirs',
    'foreign_ownership': 'rules for foreigners owning property in Tunisia',
    'debt_recovery': 'mortgages, liens, debts and recovery of receivables',
    'investment_funds': 'collective investment funds, securities and savings accounts regulation',
    'corporate': 'company law, founders, shareholders and general meetings',
    'leasing': 'rental leases, tenants and landlords rights',
}

LEGAL_SCOPE = [
    'a question about law, legal rules, regulations, taxes, contracts, rights or obligations',
    'what does Tunisian law say about this legal procedure',
    'legal rules for companies, investment funds, securities, savings accounts, debts and mortgages',
    'question juridique sur la loi, un code, un contrat, un fonds, une société ou une obligation légale',
    'سؤال قانوني حول القانون أو العقود أو الضرائب أو الشركات',
]
NON_LEGAL_SCOPE = [
    'what is the average price per square metre of apartments in a city or neighbourhood',
    'how much is my house or apartment worth, estimate its market value',
    'will property prices go up or down next year in this city',
    'which neighbourhood or city is the best place to buy property as an investment',
    'hello, hi, thanks, how are you, who are you',
    'weather forecast, sports, news or other topics unrelated to property law',
    'quel temps fera-t-il, la météo, bonjour, merci',
    'كم سعر المتر المربع، مرحبا، شكرا، الطقس',
]

_GREETING = re.compile(r"^\W*(hello|hi|hey|bonjour|salut|salam|marhaba|merci|thanks|thank you|مرحبا|شكرا)\b",
                       re.IGNORECASE)


class LegalDomainClassifier:
    NON_LEGAL_MIN = 0.45
    SCOPE_MARGIN = 0.10

    def __init__(self):
        from estatemind.assistants.shared_models import INTENT_MODEL, get_sentence_model
        self.model = get_sentence_model(INTENT_MODEL)
        enc = lambda texts: self.model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)  # noqa: E731
        self._domain_names = list(DOMAIN_DESCRIPTIONS)
        self._domain_emb = enc([DOMAIN_DESCRIPTIONS[d] for d in self._domain_names])
        self._legal_emb = enc(LEGAL_SCOPE)
        self._non_legal_emb = enc(NON_LEGAL_SCOPE)

    def classify(self, question: str) -> dict:
        from sentence_transformers import util

        q_emb = self.model.encode(question, convert_to_tensor=True, normalize_embeddings=True)
        legal = float(util.cos_sim(q_emb, self._legal_emb).max())
        non_legal = float(util.cos_sim(q_emb, self._non_legal_emb).max())

        domain_sims = util.cos_sim(q_emb, self._domain_emb)[0].tolist()
        q = question.lower()
        scores = {}
        for i, domain in enumerate(self._domain_names):
            hits = sum(1 for kw in LEGAL_DOMAINS[domain] if kw.lower() in q)
            scores[domain] = domain_sims[i] + 0.05 * min(hits, 3)
        ranked = sorted(scores, key=scores.get, reverse=True)
        keyword_hit = any(kw.lower() in q for kws in LEGAL_DOMAINS.values() for kw in kws)

        greeting = bool(_GREETING.search(question)) and len(question.split()) <= 6
        clearly_non_legal = non_legal >= self.NON_LEGAL_MIN and non_legal - legal >= self.SCOPE_MARGIN
        in_scope = not (greeting or clearly_non_legal)

        return {
            'primary_domain': ranked[0],
            'secondary_domains': ranked[1:2],
            'confidence': round(max(0.0, min(1.0, scores[ranked[0]])), 3),
            'in_scope': in_scope,
            'scope_scores': {'legal': round(legal, 3), 'non_legal': round(non_legal, 3)},
            'method': 'embedding_similarity' + ('+keywords' if keyword_hit else ''),
        }
