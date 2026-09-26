"""
Mubawab.tn scraper — major Tunisian real-estate portal.
Paginates list pages then follows listing links.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, _clean, _parse_price, _parse_surface

logger = logging.getLogger(__name__)

BASE = 'https://www.mubawab.tn'
LIST_URL_TMPL = 'https://www.mubawab.tn/fr/listing-promotion:p:{page}'
MAX_PAGES = 8


class MubawabScraper(BaseScraper):
    SOURCE_NAME = 'mubawab'
    BASE_URL = 'https://www.mubawab.tn/fr/listing-promotion:p:1'

    def discover_urls(self) -> list[str]:
        urls: list[str] = []
        for page in range(1, MAX_PAGES + 1):
            if len(urls) >= self.max_listings:
                break
            page_url = LIST_URL_TMPL.format(page=page)
            resp = self.http.get(page_url)
            if not resp:
                break
            soup = BeautifulSoup(resp.text, 'xml')
            found_on_page = 0
            # Mubawab stores the listing URL in the linkRef attribute on .listingBox li elements
            for li in soup.find_all(class_=lambda c: c and 'listingBox' in str(c)):
                href = li.get('linkRef', '').strip()
                if not href:
                    # Fallback: look for an anchor with the listing URL
                    a = li.find('a', href=True)
                    if a:
                        href = a['href'].strip()
                if not href:
                    continue
                if not href.startswith('http'):
                    href = urljoin(BASE, href)
                if href not in urls:
                    urls.append(href)
                    found_on_page += 1
                    if len(urls) >= self.max_listings:
                        break
            if found_on_page == 0:
                break  # No more pages
        return urls

    def scrape_listing(self, url: str) -> dict | None:
        resp = self.http.get(url)
        if not resp:
            return None
        try:
            return self._parse(resp.text, url)
        except Exception as exc:
            logger.warning("Mubawab parse error on %s: %s", url, exc)
            return None

    def _parse(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, 'xml')

        # Title
        title = _clean(soup.select_one('h1, .listingTitle, [class*="title"]') and
                       soup.select_one('h1, .listingTitle, [class*="title"]').get_text())

        # Price
        price_el = soup.select_one('.priceTag, [class*="price"], [class*="Price"]')
        price_raw = _clean(price_el.get_text()) if price_el else ''
        price = _parse_price(price_raw)

        # Location
        loc_el = soup.select_one('.listingLocality, .city, [class*="locality"], [class*="location"]')
        location_raw = _clean(loc_el.get_text()) if loc_el else ''

        # Description
        desc_el = soup.select_one('.listingDescription, [class*="description"], #description')
        description = _clean(desc_el.get_text()) if desc_el else ''

        # Features (bedrooms, bathrooms, surface)
        bedrooms = bathrooms = None
        surface = None
        for feat in soup.select('.features li, .icons li, [class*="feature"] li, [class*="icon"] li'):
            text = _clean(feat.get_text()).lower()
            m_bed = re.search(r'(\d+)\s*(?:ch[a]?mb|bed|pièc)', text)
            m_bath = re.search(r'(\d+)\s*(?:bain|sdb|bath)', text)
            m_surf = re.search(r'(\d+)\s*m', text)
            if m_bed and bedrooms is None:
                bedrooms = int(m_bed.group(1))
            if m_bath and bathrooms is None:
                bathrooms = int(m_bath.group(1))
            if m_surf and surface is None:
                surface = float(m_surf.group(1))

        if surface is None:
            surface = _parse_surface('', description + ' ' + (title or ''))

        # Property type
        combined = ((title or '') + ' ' + url).lower()
        property_type = 'apartment'
        for kw, pt in [
            ('terrain', 'land'), ('villa', 'villa'), ('maison', 'house'),
            ('bureau', 'office'), ('commercial', 'commercial'),
        ]:
            if kw in combined:
                property_type = pt
                break

        # Transaction type
        transaction_type = 'rent' if any(
            k in combined for k in ['louer', 'location', '/location']
        ) else 'sale'

        # Location parts
        parts = [p.strip() for p in location_raw.split(',')]
        governorate = parts[0] if parts else ''
        city = parts[1] if len(parts) > 1 else governorate

        # Image
        image_url = None
        img = soup.select_one('.mainImage img, .sliderImage img, img[class*="main"]')
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
