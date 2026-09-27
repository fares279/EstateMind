from celery import shared_task
from estatemind.assistants.legal.services.chroma_router import ChromaRouter
from estatemind.assistants.legal.services.retrieval_quality import RetrievalQualityValidator


@shared_task(name='legal.run_recall_validation')
def run_recall_validation(collection_name: str | None = None):
    # This task is a thin wrapper; chroma and embedder factories should be provided by the app context
    from django.conf import settings

    collection_name = collection_name or settings.LEGAL_RAG['CHROMA_COLLECTION']
    # Both services are module-level APIs (embed_text / query), which is the
    # interface RetrievalQualityValidator expects.
    from estatemind.assistants.legal.services import chromadb_service, embedding_service

    validator = RetrievalQualityValidator(chroma_service=chromadb_service, embedding_service=embedding_service)
    report = validator.run_full_evaluation(collection_name)
    # Persist or alert as needed; for now just return the report
    return report
