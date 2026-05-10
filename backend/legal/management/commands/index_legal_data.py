from django.core.management.base import BaseCommand
from legal.services.dataset_service import load_and_prepare
from legal.services import embedding_service, chromadb_service


class Command(BaseCommand):
    help = 'Index the Tunisian legal dataset into ChromaDB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-index even if data already exists',
        )

    def handle(self, *args, **options):
        count = chromadb_service.get_document_count()

        if count > 0 and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f'ChromaDB already contains {count} documents. '
                    'Pass --force to re-index.'
                )
            )
            return

        if options['force'] and count > 0:
            self.stdout.write('Resetting collection…')
            chromadb_service.reset_collection()

        self.stdout.write('Loading and chunking dataset…')
        chunks = load_and_prepare()
        self.stdout.write(f'  {len(chunks)} chunks prepared.')

        self.stdout.write('Generating embeddings (may take a few minutes on first run)…')
        texts = [c['text'] for c in chunks]
        embeddings = embedding_service.embed_texts(texts)

        self.stdout.write('Storing in ChromaDB…')
        added = chromadb_service.add_documents(
            ids=[c['id'] for c in chunks],
            metadatas=[c['metadata'] for c in chunks],
            documents=texts,
            embeddings=embeddings,
        )

        self.stdout.write(self.style.SUCCESS(f'Done — {added} chunks indexed.'))
