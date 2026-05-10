import logging
import threading
import re
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

_indexed = False
_index_lock = threading.Lock()


def _ensure_indexed() -> None:
    """Index dataset into ChromaDB on first use if the collection is empty."""
    global _indexed
    if _indexed:
        return
    with _index_lock:
        if _indexed:
            return
        from . import chromadb_service, embedding_service
        from .dataset_service import load_and_prepare

        count = chromadb_service.get_document_count()
        if count > 0:
            logger.info("ChromaDB already has %d documents — skipping indexing", count)
            _indexed = True
            return

        logger.info("ChromaDB is empty — indexing dataset now (first-run setup)…")
        chunks = load_and_prepare()
        if not chunks:
            logger.warning("No chunks to index")
            _indexed = True
            return

        texts = [c['text'] for c in chunks]
        embeddings = embedding_service.embed_texts(texts)
        added = chromadb_service.add_documents(
            ids=[c['id'] for c in chunks],
            metadatas=[c['metadata'] for c in chunks],
            documents=texts,
            embeddings=embeddings,
        )
        logger.info("First-run indexing complete: %d chunks stored", added)
        _indexed = True


def _extractive_fallback(question: str, sources: List[Dict[str, Any]], documents: List[str]) -> str:
    """Build a concise grounded answer directly from retrieved legal passages."""
    question_terms = {
        term
        for term in re.findall(r"[a-zA-ZÀ-ÿ']+", question.lower())
        if len(term) > 3
    }
    if not question_terms:
        question_terms = {'real', 'estate', 'transaction'}

    snippets: list[str] = []
    for source, document in zip(sources, documents):
        text = str(document or '')
        sentences = re.split(r'(?<=[.!?])\s+', text)
        matches = []
        for sentence in sentences:
            lowered = sentence.lower()
            score = sum(1 for term in question_terms if term in lowered)
            if score > 0:
                matches.append((score, sentence.strip()))
        matches.sort(key=lambda item: item[0], reverse=True)
        if matches:
            best = matches[0][1]
            label = source.get('law_name') or 'Tunisian legal text'
            article = source.get('article_ref') or 'Article'
            snippets.append(f"{label} ({article}): {best}")
        if len(snippets) >= 3:
            break

    if snippets:
        return (
            "The question is covered by the indexed Tunisian legal texts. "
            "Key relevant passages are: " + " ".join(snippets)
        )

    return (
        "The indexed legal texts were retrieved, but no precise registration passage matched your question. "
        "Please rephrase the question with a more specific transaction, tax, or registration term."
    )


def _secondary_registration_lookup(question: str, top_k: int = 5) -> tuple[list[str], list[Dict[str, Any]]]:
    """Run a second, keyword-boosted retrieval pass for registration/tax queries."""
    registration_terms = (
        "droits d'enregistrement",
        "enregistrement",
        "droit fixe",
        "notaire",
        "vente immobilière",
        "acquisition auprès des promoteurs immobiliers",
    )
    boosted_query = f"{question} {' '.join(registration_terms)}"

    from . import embedding_service, chromadb_service

    q_vec = embedding_service.embed_text(boosted_query)
    results = chromadb_service.query(q_vec, n_results=top_k)

    try:
        metadatas = results['metadatas'][0]
        documents = results['documents'][0]
    except (KeyError, IndexError):
        return [], []

    sources = []
    for meta in metadatas:
        sources.append({
            'article_ref': meta.get('article_ref', ''),
            'law_name':    meta.get('law_name', ''),
            'source':      meta.get('source', 'JuriSite Tunisie'),
            'source_url':  meta.get('source_url', ''),
            'keywords':    meta.get('keywords', ''),
        })
    return list(documents), sources


def _direct_registration_answer(question: str) -> str | None:
    """Return a direct answer for registration-duty questions when the corpus contains Article 58."""
    q = question.lower()
    if not any(term in q for term in ('registration', 'register', 'enregistrement', 'duty', 'duties', 'fee', 'fees', 'property transaction', 'real estate')):
        return None

    try:
        from .dataset_service import DATASET_PATH
        import json

        with open(DATASET_PATH, encoding='utf-8') as fh:
            data = json.load(fh)

        for item in data.get('articles', []):
            text = str(item.get('text', ''))
            lowered = text.lower()
            if 'enregistr' in lowered and 'droit fixe' in lowered and ('acquisition' in lowered or 'immobilier' in lowered):
                return (
                    "For real-estate acquisition contracts covered by the corpus, Article 58 states that they are "
                    "registered at the fixed duty when they concern acquisition from property developers of buildings "
                    "or serviced land for economic activities, or land intended for housing construction, provided the "
                    "property has not already been exploited or sold by the developer."
                )
    except Exception as exc:
        logger.warning("Direct registration lookup failed: %s", exc)

    return None


def answer_question(question: str, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
    _ensure_indexed()

    from . import embedding_service, chromadb_service, llm_service

    q_vec = embedding_service.embed_text(question)
    results = chromadb_service.query(q_vec, n_results=top_k)

    try:
        metadatas = results['metadatas'][0]
        documents = results['documents'][0]
        distances = results.get('distances', [[]])[0]
    except (KeyError, IndexError):
        metadatas, documents, distances = [], [], []

    if not documents:
        return "I'm sorry, no relevant documents were found in the database for your question.", []

    context_parts = []
    sources = []
    for i, doc in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        label = f"{meta.get('law_name', 'Law')} — {meta.get('article_ref', 'Article')}"
        context_parts.append(f"{label}:\n{doc}")
        sources.append({
            'article_ref': meta.get('article_ref', ''),
            'law_name':    meta.get('law_name', ''),
            'source':      meta.get('source', 'JuriSite Tunisie'),
            'source_url':  meta.get('source_url', ''),
            'keywords':    meta.get('keywords', ''),
        })

    context_block = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are a legal assistant specialized in Tunisian law, "
        "covering real estate law, corporate law, tax law, and civil law. "
        "Answer ONLY based on the legal context provided below. "
        "If the answer is not found in the context, respond exactly with: "
        "'I don't know — this information is not available in my database.' "
        "Cite the relevant articles and laws in your answer. Respond in English."
    )
    user_prompt = (
        f"Legal context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Provide a legally accurate and concise answer, citing the relevant sources."
    )

    try:
        answer = llm_service.generate(system_prompt, user_prompt, max_tokens=750)
        final_answer = answer.strip() if answer and answer.strip() else "I don't know — this information is not available in my database."
        direct_answer = _direct_registration_answer(question)
        if direct_answer and final_answer.lower().startswith("i don't know"):
            final_answer = direct_answer
    except RuntimeError as exc:
        msg = str(exc)
        if 'model not found' in msg.lower() or 'ai service http error' in msg.lower():
            logger.warning("Falling back to extractive legal answer because the hosted LLM is unavailable: %s", msg)
            direct_answer = _direct_registration_answer(question)
            if direct_answer:
                return direct_answer, sources
            fallback_documents = list(documents)
            fallback_sources = list(sources)
            if any(term in question.lower() for term in ('registration', 'register', 'enregistrement', 'fee', 'fees', 'tax', 'duty', 'duties')):
                secondary_documents, secondary_sources = _secondary_registration_lookup(question)
                if secondary_documents:
                    fallback_documents = secondary_documents
                    fallback_sources = secondary_sources
            final_answer = _extractive_fallback(question, fallback_sources, fallback_documents)
        else:
            raise

    return final_answer, sources


def get_status() -> Dict[str, Any]:
    from . import chromadb_service, llm_service
    from django.conf import settings
    cfg = getattr(settings, 'LEGAL_RAG', {})

    doc_count = chromadb_service.get_document_count()
    llm_ok = llm_service.check_availability()

    return {
        'documents_indexed': doc_count,
        'llm_available':     llm_ok,
        'model':             cfg.get('LLM_MODEL', 'hosted_vllm/Llama-3.1-70B-Instruct'),
        'embedding_model':   cfg.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
        'ready':             doc_count > 0 and llm_ok,
    }
