"""Builds a new versioned ChromaDB collection and activates it only if it retrieves well.

Collections are never overwritten: each build gets a new name, is validated
with RetrievalQualityValidator on data/eval_questions.json, and replaces the
active collection only when it meets the recall targets. The previous
collection stays on disk (status 'retired') for rollback.
"""
from importlib.metadata import PackageNotFoundError, version

from django.utils import timezone

from estatemind.assistants.legal.models import EmbeddingCollectionVersion

from . import chromadb_service, embedding_service
from .dataset_service import load_domain_corpus
from .retrieval_quality import RetrievalQualityValidator

CORPUS_DOMAIN = 'all'


class CollectionUpgrader:
    def _next_name(self, domain: str) -> str:
        n = EmbeddingCollectionVersion.objects.filter(domain=domain).count() + 1
        existing = set(chromadb_service.list_collection_names())
        name = f"legal_tunisia_{domain}_v{n}"
        while EmbeddingCollectionVersion.objects.filter(collection_name=name).exists() or name in existing:
            n += 1
            name = f"legal_tunisia_{domain}_v{n}"
        return name

    @staticmethod
    def _library_version() -> str:
        try:
            return version('sentence-transformers')
        except PackageNotFoundError:
            return 'unknown'

    def upgrade(self, domain: str = CORPUS_DOMAIN, activate: bool = True) -> dict:
        model = embedding_service.model_name()
        name = self._next_name(domain)
        record = EmbeddingCollectionVersion.objects.create(
            collection_name=name, domain=domain, embedding_model=model,
            embedding_version=self._library_version(), total_passages=0,
            indexed_date=timezone.now().date(), status='indexing', is_active=False,
        )

        chunks = load_domain_corpus(domain)
        texts = [c['text'] for c in chunks]
        count = chromadb_service.index_collection(
            name, ids=[c['id'] for c in chunks], metadatas=[c['metadata'] for c in chunks],
            documents=texts, embeddings=embedding_service.embed_texts(texts),
        )
        record.total_passages = count
        record.status = 'validating'
        record.save(update_fields=['total_passages', 'status'])

        report = RetrievalQualityValidator(chromadb_service, embedding_service).run_full_evaluation(name)
        record.recall_at_5 = report['recall_at_5']
        record.notes = (f"recall@1={report['recall_at_1']} recall@3={report['recall_at_3']} "
                        f"by_lang={report['recall_at_3_by_language']} "
                        f"gate: answerable_pass={report['gate_answerable_pass_rate']} "
                        f"negative_block={report['gate_negative_block_rate']}")

        if not report['passed']:
            record.status = 'failed'
            record.save(update_fields=['recall_at_5', 'notes', 'status'])
            return {'status': 'upgrade_rejected', 'collection': name, 'report': report}

        if not activate:
            record.status = 'validated'
            record.save(update_fields=['recall_at_5', 'notes', 'status'])
            return {'status': 'validated_not_activated', 'collection': name, 'report': report}

        previous = list(EmbeddingCollectionVersion.objects.filter(is_active=True).exclude(pk=record.pk))
        for old in previous:
            old.is_active = False
            old.status = 'retired'
            old.save(update_fields=['is_active', 'status'])
        record.is_active = True
        record.status = 'active'
        record.save(update_fields=['recall_at_5', 'notes', 'status', 'is_active'])
        return {'status': 'upgrade_complete', 'collection': name, 'passages': count,
                'retired': [o.collection_name for o in previous], 'report': report}
