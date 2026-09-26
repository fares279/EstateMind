"""
Tecnocasa.tn scraper — franchise real-estate agency listings.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, _clean, _parse_price, _parse_surface

logger = logging.getLogger(__name__)

BASE = 'https://www.tecnocasa.tn'
LIST_PAGES = [
    'https://www.tecnocasa.tn/vendre/immeubles/nord-est-ne/grand-tunis.html',
    'https://www.tecnocasa.tn/vendre/appartements/nord-est-ne/grand-tunis.html',
    'https://www.tecnocasa.tn/vendre/maisons-villas/nord-est-ne/grand-tunis.html',
    'https://www.tecnocasa.tn/vendre/terrains/nord-est-ne/grand-tunis.html',
    'https://www.tecnocasa.tn/louer/appartements/nord-est-ne/grand-tunis.html',
]


class TecnocasaScraper(BaseScraper):
    SOURCE_NAME = 'tecnocasa'
    BASE_URL = LIST_PAGES[0]

    def discover_urls(self) -> list[str]:
        urls: list[str] = []
        for page_url in LIST_PAGES:
            if len(urls) >= self.max_listings:
                break
            resp = self.http.get(page_url)
            if not resp:
                continue
            soup = BeautifulSoup(resp.text, 'lxml')
            for a in soup.select('a[href]'):
                href = a['href'].strip()
                if not href.startswith('http'):
                    href = urljoin(BASE, href)
                if (
                    'tecnocasa.tn' in href
                    and any(seg in href for seg in ['/annonce/', '/property/', '/bien/'])
                    and href not in urls
                ):
                    urls.append(href)
                    if len(urls) >= self.max_listings:
                        break
            # Fallback: grab all links that look like detail pages
            if not urls:
                links = self.extract_candidate_links(resp.text, page_url)
                for link in links:
                    if 'tecnocasa.tn' in link and link not in urls:
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
            logger.warning("Tecnocasa parse error on %s: %s", url, exc)
            return None

    def _parse(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, 'lxml')

        title = _clean(soup.select_one('h1, .property-title, [class*="title"]') and
                       soup.select_one('h1, .property-title, [class*="title"]').get_text())

        price_el = soup.select_one('.price, [class*="price"]')
        price_raw = _clean(price_el.get_text()) if price_el else ''
        price = _parse_price(price_raw)

        desc_el = soup.select_one('.description, [class*="desc"]')
        description = _clean(desc_el.get_text()) if desc_el else ''

        # Surface and rooms
        surface = bathrooms = bedrooms = None
        for el in soup.select('.property-feature, [class*="feature"], [class*="detail"] li'):
            text = _clean(el.get_text()).lower()
            m_s = re.search(r'(\d+)\s*m', text)
            m_b = re.search(r'(\d+)\s*(?:ch[a]?mb|bed)', text)
            m_bt = re.search(r'(\d+)\s*(?:bain|sdb|bath)', text)
            if m_s and surface is None:
                surface = float(m_s.group(1))
            if m_b and bedrooms is None:
                bedrooms = int(m_b.group(1))
            if m_bt and bathrooms is None:
                bathrooms = int(m_bt.group(1))

        if surface is None:
            surface = _parse_surface('', description + ' ' + (title or ''))

        # Location from breadcrumb or meta
        location_raw = ''
        for sel in ('.breadcrumb', 'nav[aria-label]', '[class*="location"]', '[class*="address"]'):
            el = soup.select_one(sel)
            if el:
                location_raw = _clean(el.get_text())
                break

        parts = [p.strip() for p in location_raw.split(',') if p.strip()]
        governorate = 'Tunis'  # Tecnocasa is mainly Grand Tunis focused
        city = parts[-1] if parts else 'Tunis'

        # Type from URL
        combined = url.lower() + ' ' + (title or '').lower()
        property_type = 'apartment'
        for kw, pt in [
            ('terrain', 'land'), ('villa', 'villa'), ('maison', 'house'),
            ('bureau', 'office'), ('commercial', 'commercial'),
        ]:
            if kw in combined:
                property_type = pt
                break

        transaction_type = 'rent' if '/louer/' in url else 'sale'

        image_url = None
        img = soup.select_one('img.property-image, img[class*="main"], .gallery img')
        if img:
            image_url = img.get('src') or img.get('data-src')

        if not title:
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
            'neighborhood': '',
            'location_raw': location_raw,
            'property_type': property_type,
            'transaction_type': transaction_type,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'image_url': image_url,
        }
