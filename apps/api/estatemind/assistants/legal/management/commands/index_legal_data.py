import json

from django.core.management.base import BaseCommand

from estatemind.assistants.legal.services.collection_upgrader import CollectionUpgrader


class Command(BaseCommand):
    help = ('Index the Tunisian legal dataset into a new versioned ChromaDB collection with the '
            'configured embedding model, validate retrieval, and activate it if it passes.')

    def add_arguments(self, parser):
        parser.add_argument('--no-activate', action='store_true',
                            help='Build and validate, but keep the current collection active.')

    def handle(self, *args, **options):
        self.stdout.write('Building a new legal collection (the active one is not modified)…')
        result = CollectionUpgrader().upgrade(activate=not options['no_activate'])
        report = result['report']
        style = self.style.SUCCESS if report['passed'] else self.style.ERROR
        self.stdout.write(style(f"{result['status']}: {result['collection']}"))
        self.stdout.write(json.dumps({k: v for k, v in report.items() if k != 'failures'}, indent=1,
                                     ensure_ascii=False))
        for f in report['failures']:
            self.stdout.write(f"  missed {f['id']}: gold {f['gold']} got {f['retrieved_articles']} "
                              f"(top sim {f['top_similarity']})")
