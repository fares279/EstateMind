"""
Tayara.tn scraper — Tunisia's largest classifieds platform.
Uses requests + BeautifulSoup (Playwright optional for JS-heavy pagination).
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, RequestManager, _clean, _parse_price, _parse_surface, is_listing_url

logger = logging.getLogger(__name__)

LIST_PAGES = [
    'https://www.tayara.tn/c/immobilier/',
    'https://www.tayara.tn/c/immobilier/?page=2',
    'https://www.tayara.tn/c/immobilier/?page=3',
    'https://www.tayara.tn/c/immobilier/?page=4',
    'https://www.tayara.tn/c/immobilier/?page=5',
]


class TayaraScraper(BaseScraper):
    SOURCE_NAME = 'tayara'
    BASE_URL = 'https://www.tayara.tn/c/immobilier/'

    def discover_urls(self) -> list[str]:
        urls: list[str] = []
        for page_url in LIST_PAGES:
            if len(urls) >= self.max_listings:
                break
            resp = self.http.get(page_url)
            if not resp:
                continue
            links = self.extract_candidate_links(resp.text, page_url)
            for link in links:
                if is_listing_url(link) and 'tayara.tn' in link and link not in urls:
                    urls.append(link)
                    if len(urls) >= self.max_listings:
                        break
        return urls

    def scrape_listing(self, url: str) -> dict | None:
        resp = self.http.get(url)
        if not resp:
            return None
        try:
            return self._parse(resp.text, url)
        except Exception as exc:
            logger.warning("Tayara parse error on %s: %s", url, exc)
            return None

    def _parse(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, 'lxml')

        # Title
        title = ''
        for sel in ('h1', '.ad-title', '.title', '[class*="title"]'):
            el = soup.select_one(sel)
            if el:
                title = _clean(el.get_text())
                break

        # Price
        price_raw = ''
        for sel in ('.price', '.ad-price', '[class*="price"]', '[class*="Price"]'):
            el = soup.select_one(sel)
            if el:
                price_raw = _clean(el.get_text())
                break
        price = _parse_price(price_raw)

        # Location
        location_raw = ''
        for sel in ('.location', '.ad-location', '.city', '[class*="location"]', '[class*="city"]'):
            el = soup.select_one(sel)
            if el:
                location_raw = _clean(el.get_text())
                break

        # Description
        description = ''
        for sel in ('.description', '#description', '[class*="description"]', '[class*="desc"]'):
            el = soup.select_one(sel)
            if el:
                description = _clean(el.get_text())
                break

        # Surface from description
        surface = _parse_surface('', description + ' ' + title)

        # Governorate / city
        parts = [p.strip() for p in location_raw.split(',')]
        governorate = parts[0] if parts else ''
        city = parts[1] if len(parts) > 1 else governorate

        # Property type from title/URL
        combined = (title + ' ' + url).lower()
        property_type = 'apartment'
        for kw, pt in [
            ('terrain', 'land'), ('villa', 'villa'), ('maison', 'house'),
            ('bureau', 'office'), ('commercial', 'commercial'),
        ]:
            if kw in combined:
                property_type = pt
                break

        # Image
        image_url = None
        img = soup.select_one('img[src*="tayara"]') or soup.select_one('.ad-image img')
        if img:
            image_url = img.get('src') or img.get('data-src')

        if not title and not price:
            return None

        return {
            'source': self.SOURCE_NAME,
            'listing_url': url,
            'title': title,
            'description': description,
            'price': price_raw,
            'price_tnd': price,
            'surface_area': '',
            'surface_m2': surface,
            'governorate': governorate,
            'city': city,
            'neighborhood': parts[2] if len(parts) > 2 else '',
            'location_raw': location_raw,
            'property_type': property_type,
            'transaction_type': 'rent' if 'louer' in combined else 'sale',
            'bedrooms': None,
            'bathrooms': None,
            'image_url': image_url,
        }
