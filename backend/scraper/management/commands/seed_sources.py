"""
Management command: seed_sources

Populates the ScrapeSource table with the five production sources.
Safe to run multiple times (uses get_or_create).

Usage
-----
python manage.py seed_sources
"""

from django.core.management.base import BaseCommand

SOURCES = [
    {
        'name': 'tayara',
        'base_url': 'https://www.tayara.tn/c/immobilier/',
        'scraper_class': 'TayaraScraper',
        'max_listings': 150,
        'schedule_hours': 12,
    },
    {
        'name': 'mubawab',
        'base_url': 'https://www.mubawab.tn/fr/listing-promotion:p:1',
        'scraper_class': 'MubawabScraper',
        'max_listings': 120,
        'schedule_hours': 24,
    },
    {
        'name': 'tunisie_annonce',
        'base_url': 'http://www.tunisie-annonce.com/AnnoncesImmobilier.asp',
        'scraper_class': 'TunisieAnnonceScraper',
        'max_listings': 80,
        'schedule_hours': 24,
    },
    {
        'name': 'tecnocasa',
        'base_url': 'https://www.tecnocasa.tn/vendre/immeubles/nord-est-ne/grand-tunis.html',
        'scraper_class': 'TecnocasaScraper',
        'max_listings': 80,
        'schedule_hours': 48,
    },
    {
        'name': 'bigdatis',
        'base_url': 'https://bigdatis.tn/immobilier/vente/appartement/',
        'scraper_class': 'BigdatisScraper',
        'max_listings': 100,
        'schedule_hours': 24,
    },
]


class Command(BaseCommand):
    help = 'Seed the ScrapeSource table with the five production scraping sources'

    def handle(self, *args, **options):
        from scraper.models import ScrapeSource
        created_count = 0
        for data in SOURCES:
            obj, created = ScrapeSource.objects.get_or_create(
                name=data['name'],
                defaults={
                    'base_url': data['base_url'],
                    'scraper_class': data['scraper_class'],
                    'max_listings': data['max_listings'],
                    'schedule_hours': data['schedule_hours'],
                    'is_active': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created source: {obj.name}"))
            else:
                self.stdout.write(f"  Exists:         {obj.name}")

        self.stdout.write(
            self.style.SUCCESS(f"\nSeeded {created_count} new source(s). Total: {len(SOURCES)}.\n")
        )
