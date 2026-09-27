"""Retrieves legal passages for a question and decides whether they are relevant enough.

Mirrors chatbot.MarketDataRetriever's role: produce the grounding context the
answer may use, or say there is none.
"""
import logging
from dataclasses import dataclass, field

from . import chromadb_service, embedding_service
from .chroma_router import ChromaRouter

logger = logging.getLogger(__name__)


@dataclass
class Passage:
    rank: int
    text: str
    similarity: float
    metadata: dict

    @property
    def source_id(self) -> str:
        return str(self.metadata.get('chunk_id') or self.metadata.get('id') or f'doc_{self.rank}')

    @property
    def label(self) -> str:
        law = self.metadata.get('law_name', '')
        art = self.metadata.get('article_ref', '')
        return ', '.join(x for x in (law, art) if x) or 'Legal source'


@dataclass
class RetrievalResult:
    passages: list[Passage]
    collection: str
    embedding_model: str
    top_similarity: float
    sufficient: bool
    context_passages: list[Passage] = field(default_factory=list)


class LegalRetriever:
    def __init__(self):
        from django.conf import settings
        cfg = getattr(settings, 'LEGAL_RAG', {})
        self.router = ChromaRouter()
        self.top_k = cfg.get('RETRIEVAL_TOP_K', 5)
        self.max_context = cfg.get('RETRIEVAL_MAX_CONTEXT', 4)
        # Below MIN_SIMILARITY for the best passage, the corpus does not cover
        # the question and no answer is generated. Passages more than
        # CONTEXT_MARGIN below the best one are not given to the model.
        self.min_similarity = cfg.get('RETRIEVAL_MIN_SIMILARITY', 0.52)
        self.context_margin = cfg.get('RETRIEVAL_CONTEXT_MARGIN', 0.05)

    def warm_up(self):
        embedding_service.embed_text('warm-up')

    def retrieve(self, query: str, domain: str) -> RetrievalResult:
        route = self.router.route(domain)
        qvec = embedding_service.embed_text(query)
        raw = chromadb_service.query(qvec, n_results=self.top_k, collection_name=route.collection)
        docs = raw.get('documents', [[]])[0]
        metas = raw.get('metadatas', [[]])[0]
        dists = raw.get('distances', [[]])[0]
        passages = [
            Passage(rank=i + 1, text=doc, similarity=round(1.0 - float(dists[i]), 4), metadata=metas[i] or {})
            for i, doc in enumerate(docs)
        ]
        top = passages[0].similarity if passages else 0.0
        context = [p for p in passages if p.similarity >= top - self.context_margin][: self.max_context]
        return RetrievalResult(
            passages=passages,
            collection=route.collection,
            embedding_model=route.embedding_model,
            top_similarity=top,
            sufficient=bool(passages) and top >= self.min_similarity,
            context_passages=context,
        )
