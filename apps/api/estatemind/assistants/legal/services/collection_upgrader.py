from django.utils import timezone
from estatemind.assistants.legal.models import EmbeddingCollectionVersion
from .retrieval_quality import RetrievalQualityValidator
from .chroma_router import ChromaRouter


class CollectionUpgrader:
    def __init__(self, chroma, embedder_factory):
        self.chroma = chroma
        self.embedder_factory = embedder_factory
        self.router = ChromaRouter()

    def _next_version(self, domain: str) -> int:
        base = EmbeddingCollectionVersion.objects.filter(domain=domain).count()
        return base + 1

    def _get_model_version(self, model_name: str) -> str:
        # Simplified: return a placeholder; in real setups query the model package metadata
        return '1.0.0'

    def upgrade_domain(self, domain: str, new_embedding_model: str) -> dict:
        current_active = EmbeddingCollectionVersion.objects.filter(domain=domain, is_active=True).first()
        new_version_number = self._next_version(domain)
        new_collection_name = f"legal_tunisia_{domain}_v{new_version_number}"

        new_version_record = EmbeddingCollectionVersion.objects.create(
            collection_name=new_collection_name,
            domain=domain,
            embedding_model=new_embedding_model,
            embedding_version=self._get_model_version(new_embedding_model),
            total_passages=0,
            indexed_date=timezone.now().date(),
            status='indexing',
            is_active=False,
        )

        passages = self._load_domain_corpus(domain)
        # Indexing is delegated to chroma service (assumed to exist)
        self.chroma.index_passages(collection_name=new_collection_name, passages=passages, embedder=new_embedding_model)

        new_version_record.total_passages = len(passages)
        new_version_record.status = 'validating'
        new_version_record.save()

        validator = RetrievalQualityValidator(chroma_service=self.chroma, embedding_service=self.embedder_factory(new_embedding_model))
        report = validator.run_full_evaluation(new_collection_name)
        new_version_record.recall_at_5 = report['recall_at_5']

        if not report['passed']:
            new_version_record.status = 'failed'
            new_version_record.save()
            return {'status': 'upgrade_rejected', 'reason': f"Recall@5 = {report['recall_at_5']:.1%} below target", 'report': report}

        if current_active:
            current_active.is_active = False
            current_active.status = 'retired'
            current_active.save()

        new_version_record.is_active = True
        new_version_record.status = 'active'
        new_version_record.save()

        return {'status': 'upgrade_complete', 'new_collection': new_collection_name, 'recall_at_5': report['recall_at_5'], 'passages': len(passages)}

    def _load_domain_corpus(self, domain: str) -> list:
        # Hook: load canonical domain corpus from storage. For now, raise if empty.
        from estatemind.assistants.legal.services.dataset_service import load_domain_corpus
        return load_domain_corpus(domain)
