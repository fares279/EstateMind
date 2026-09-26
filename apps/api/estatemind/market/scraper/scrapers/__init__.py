from .tayara import TayaraScraper
from .mubawab import MubawabScraper
from .tunisie_annonce import TunisieAnnonceScraper
from .tecnocasa import TecnocasaScraper
from .bigdatis import BigdatisScraper

# Registry maps scraper_class string (stored in ScrapeSource model) → class
SCRAPER_REGISTRY = {
    'TayaraScraper': TayaraScraper,
    'MubawabScraper': MubawabScraper,
    'TunisieAnnonceScraper': TunisieAnnonceScraper,
    'TecnocasaScraper': TecnocasaScraper,
    'BigdatisScraper': BigdatisScraper,
}


def get_scraper_class(name: str):
    klass = SCRAPER_REGISTRY.get(name)
    if klass is None:
        raise ValueError(f"Unknown scraper class '{name}'. Available: {list(SCRAPER_REGISTRY)}")
    return klass
