import logging
from typing import List, Dict, Any

from .chroma_router import ChromaRouter
from .domain_classifier import LegalDomainClassifier
from .hallucination_detector import HallucinationDetector
from .citation_builder import Citation
from . import chromadb_service, embedding_service

logger = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self):
        self.router = ChromaRouter()
        self.classifier = LegalDomainClassifier()
        self.detector = HallucinationDetector()

    def _embed(self, text: str, model_name: str):
        # embedding_service wraps SentenceTransformers; ensure model parity externally
        return embedding_service.embed_text(text)

    def _generate(self, question: str, passages: List[str]):
        # Defer to existing llm_service to keep consistent API
        from . import llm_service
        system_prompt = (
            "You are a legal assistant specialized in Tunisian law. Answer ONLY based on provided passages."
        )
        user_prompt = f"Context:\n{''.join(passages)}\n\nQuestion: {question}"
        try:
            return llm_service.generate(system_prompt, user_prompt, max_tokens=750)
        except Exception as exc:
            logger.warning("LLM generate failed: %s", exc)
            raise

    def ask(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        # 1. classify
        domain_res = self.classifier.classify(question)
        primary = domain_res.get('primary_domain')

        # 2. route
        collection = self.router.get_active_collection(primary)
        embed_model = self.router.get_embedding_model_for_query(primary)

        # 3. embed
        qvec = self._embed(question, embed_model)

        # 4. retrieve
        retrieved = chromadb_service.query(qvec, n_results=top_k, collection_name=collection)
        metadatas = retrieved.get('metadatas', [[]])[0]
        documents = retrieved.get('documents', [[]])[0]
        distances = retrieved.get('distances', [[]])[0]

        # Build passages
        passages = [d for d in documents]

        # 5. generate
        answer_text = self._generate(question, passages)

        # 6. hallucination check
        grounding = self.detector.check_answer(answer_text, passages)

        # 7. build citations
        citations = []
        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            sim = 1.0 - distances[i] if distances and i < len(distances) else 0.0
            c = Citation(
                source_id=meta.get('id', f'doc_{i}'),
                law_name=meta.get('law_name', ''),
                article=meta.get('article_ref', ''),
                passage_text=doc,
                similarity=sim,
                rank=i+1,
            )
            citations.append(c)

        grounding_score = grounding.get('average_score', 0.0)
        grounding_label = 'HIGH' if grounding_score >= 0.85 else 'MEDIUM' if grounding_score >= 0.65 else 'LOW'

        return {
            'answer_text': answer_text,
            'sentences': grounding.get('sentences', []),
            'grounding_score': grounding_score,
            'grounding_label': grounding_label,
            'citations': [c.to_dict() for c in citations],
            'domain': primary,
            'collection_used': collection,
        }


def ask_question(question: str) -> (str, List[Dict[str, Any]]):
    engine = RAGEngine()
    res = engine.ask(question)
    return res.get('answer_text', ''), res.get('citations', [])


def get_status() -> Dict[str, Any]:
    engine = RAGEngine()
    from . import chromadb_service, llm_service
    return {
        'documents_indexed': chromadb_service.get_document_count(),
        'llm_available': llm_service.check_availability(),
        'ready': chromadb_service.get_document_count() > 0 and llm_service.check_availability(),
    }
