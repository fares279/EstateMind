"""
BigDatis.tn scraper — Tunisian property portal.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, _clean, _parse_price, _parse_surface

logger = logging.getLogger(__name__)

BASE = 'https://bigdatis.tn'
LIST_PAGES = [
    'https://bigdatis.tn/immobilier/vente/appartement/',
    'https://bigdatis.tn/immobilier/vente/maison/',
    'https://bigdatis.tn/immobilier/vente/terrain/',
    'https://bigdatis.tn/immobilier/location/appartement/',
    'https://bigdatis.tn/immobilier/location/maison/',
]


class BigdatisScraper(BaseScraper):
    SOURCE_NAME = 'bigdatis'
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
                    'bigdatis.tn' in href
                    and len(href) > len(BASE) + 10
                    and href not in urls
                    and href not in LIST_PAGES
                ):
                    urls.append(href)
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
            logger.warning("BigDatis parse error on %s: %s", url, exc)
            return None

    def _parse(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, 'lxml')

        title_el = soup.select_one('h1, .property-title, .listing-title, [class*="title"]')
        title = _clean(title_el.get_text()) if title_el else ''

        price_el = soup.select_one('.price, [class*="price"]')
        price_raw = _clean(price_el.get_text()) if price_el else ''
        price = _parse_price(price_raw)

        desc_el = soup.select_one('.description, [class*="description"], #description')
        description = _clean(desc_el.get_text()) if desc_el else ''

        surface = bedrooms = bathrooms = None
        for el in soup.select('[class*="feature"], [class*="detail"], .spec, li'):
            text = _clean(el.get_text()).lower()
            m_s = re.search(r'(\d+)\s*m', text)
            m_b = re.search(r'(\d+)\s*(?:chambre|bed)', text)
            m_bt = re.search(r'(\d+)\s*(?:bain|sdb|bath)', text)
            if m_s and surface is None:
                surface = float(m_s.group(1))
            if m_b and bedrooms is None:
                bedrooms = int(m_b.group(1))
            if m_bt and bathrooms is None:
                bathrooms = int(m_bt.group(1))

        if surface is None:
            surface = _parse_surface('', description + ' ' + (title or ''))

        loc_el = soup.select_one('[class*="location"], [class*="city"], [class*="address"]')
        location_raw = _clean(loc_el.get_text()) if loc_el else ''
        parts = [p.strip() for p in location_raw.split(',') if p.strip()]
        governorate = parts[0] if parts else ''
        city = parts[1] if len(parts) > 1 else governorate

        combined = url.lower() + ' ' + (title or '').lower()
        property_type = 'apartment'
        for kw, pt in [
            ('terrain', 'land'), ('villa', 'villa'), ('maison', 'house'),
            ('bureau', 'office'), ('commercial', 'commercial'),
        ]:
            if kw in combined:
                property_type = pt
                break

        transaction_type = 'rent' if '/location/' in url or 'louer' in combined else 'sale'

        image_url = None
        img = soup.select_one('img[class*="main"], .gallery img, img[src*="bigdatis"]')
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
            'neighborhood': parts[2] if len(parts) > 2 else '',
            'location_raw': location_raw,
            'property_type': property_type,
            'transaction_type': transaction_type,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'image_url': image_url,
        }
