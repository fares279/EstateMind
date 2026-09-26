from celery import shared_task
from estatemind.assistants.legal.services.chroma_router import ChromaRouter
from estatemind.assistants.legal.services.retrieval_quality import RetrievalQualityValidator


@shared_task(name='legal.run_recall_validation')
def run_recall_validation(collection_name: str):
    # This task is a thin wrapper; chroma and embedder factories should be provided by the app context
    from estatemind.assistants.legal.services.chromadb_service import ChromaService
    from estatemind.assistants.legal.services.embedding_service import EmbeddingService

    chroma = ChromaService()
    embedder = EmbeddingService()
    validator = RetrievalQualityValidator(chroma_service=chroma, embedding_service=embedder)
    report = validator.run_full_evaluation(collection_name)
    # Persist or alert as needed; for now just return the report
    return report
