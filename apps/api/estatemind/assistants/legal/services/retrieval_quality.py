from dataclasses import dataclass
from typing import List

@dataclass
class LegalTestCase:
    question: str
    domain: str
    correct_source_id: str
    correct_law: str
    difficulty: str


# Curated test set using real Chroma document IDs from the current corpus.
LEGAL_TEST_SET: List[LegalTestCase] = [
    LegalTestCase(
        question="What are the conditions for investment savings account deposits?",
        domain="investment",
        correct_source_id="d28d1c0fdab3a82c",
        correct_law="Loi sur l'Épargne-Investissement, Art. 3",
        difficulty="easy",
    ),
    LegalTestCase(
        question="What does article 7 say about bank and client delegation powers?",
        domain="taxation",
        correct_source_id="6b202861c0c91e61",
        correct_law="Code de l'Impôt sur le Revenu, Art.7",
        difficulty="easy",
    ),
    LegalTestCase(
        question="What operations do debt collection companies perform under article 9?",
        domain="debt_recovery",
        correct_source_id="d3a715c2268af4d1",
        correct_law="Code du Recouvrement des Créances, Art. 9",
        difficulty="easy",
    ),
    LegalTestCase(
        question="When does debt assignment take effect against the debtor under article 11?",
        domain="debt_recovery",
        correct_source_id="b3c91566ffb2caaa",
        correct_law="Code du Recouvrement des Créances, Art. 11",
        difficulty="medium",
    ),
    LegalTestCase(
        question="Which company notifies the debtor first when several firms are assigned the same claim?",
        domain="debt_recovery",
        correct_source_id="0c1eeec3c7e254a7",
        correct_law="Code du Recouvrement des Créances, Art. 13",
        difficulty="medium",
    ),
    LegalTestCase(
        question="What does Article 58 say about contracts for acquisition from property developers of buildings or serviced land?",
        domain="transactions",
        correct_source_id="5f68aee0ddbd255a",
        correct_law="Code d'Incitation aux Investissements, Art. 58",
        difficulty="easy",
    ),
    LegalTestCase(
        question="Within fifteen days from the close of subscription, what must the founders do according to Article 171?",
        domain="corporate",
        correct_source_id="8d263ddddcf4cf5f",
        correct_law="Code des Sociétés, Article 171",
        difficulty="medium",
    ),
    LegalTestCase(
        question="When is VAT restitution performed under Article 15 of the VAT code?",
        domain="taxation",
        correct_source_id="712aa145a5801adc",
        correct_law="Législation Tunisienne, article 15 du code de la TVA",
        difficulty="easy",
    ),
    LegalTestCase(
        question="What benefits are not withdrawn under Article 65 of the investment incentive code?",
        domain="investment",
        correct_source_id="d089c11374608d33",
        correct_law="Code d'Incitation aux Investissements, article 65du",
        difficulty="medium",
    ),
    LegalTestCase(
        question="What happens to benefits under Article 65 of the investment incentive code when conditions change?",
        domain="investment",
        correct_source_id="39230b046761024d",
        correct_law="Code d'Incitation aux Investissements, article 65 du",
        difficulty="medium",
    ),
]


class RetrievalQualityValidator:
    TARGET_RECALL = 0.90
    K = 5

    def __init__(self, chroma_service, embedding_service):
        self.chroma = chroma_service
        self.embedder = embedding_service

    def run_full_evaluation(self, collection_name: str) -> dict:
        results = []
        failures = []

        for tc in LEGAL_TEST_SET:
            res = self._evaluate_single(tc, collection_name)
            results.append(res)
            if not res['found']:
                failures.append({
                    'question': tc.question,
                    'domain': tc.domain,
                    'correct_law': tc.correct_law,
                    'difficulty': tc.difficulty,
                    'top_retrieved': res['top_retrieved_ids'],
                })

        recall_at_k = sum(r['found'] for r in results) / max(1, len(results))
        passed = recall_at_k >= self.TARGET_RECALL

        return {
            'collection': collection_name,
            'recall_at_5': round(recall_at_k, 3),
            'target': self.TARGET_RECALL,
            'passed': passed,
            'total_questions': len(results),
            'found': sum(r['found'] for r in results),
            'missed': len(failures),
            'failures': failures,
        }

    def _evaluate_single(self, test_case: LegalTestCase, collection_name: str) -> dict:
        # embed the question
        qvec = self.embedder.embed_text(test_case.question)
        # query the specific collection
        retrieved = self.chroma.query(qvec, n_results=self.K, collection_name=collection_name)
        retrieved_ids = retrieved.get('ids', [[]])[0] if retrieved.get('ids') else []
        # normalize ids
        retrieved_ids = [str(i) for i in retrieved_ids]
        found = test_case.correct_source_id in retrieved_ids
        return {
            'question_id': test_case.correct_source_id,
            'domain': test_case.domain,
            'difficulty': test_case.difficulty,
            'found': bool(found),
            'top_retrieved_ids': retrieved_ids,
            'rank': (retrieved_ids.index(test_case.correct_source_id) + 1) if found else None,
        }
