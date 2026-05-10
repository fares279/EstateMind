"""
Tunisie-Annonce.com scraper — legacy table-based classifieds site.
Follows 'Détails' links from the listing index to get full descriptions.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, _clean, _parse_price, _parse_surface

logger = logging.getLogger(__name__)

BASE = 'http://www.tunisie-annonce.com'
LIST_URL = 'http://www.tunisie-annonce.com/AnnoncesImmobilier.asp'


class TunisieAnnonceScraper(BaseScraper):
    SOURCE_NAME = 'tunisie_annonce'
    BASE_URL = LIST_URL

    def discover_urls(self) -> list[str]:
        urls: list[str] = []
        page = 1
        while len(urls) < self.max_listings:
            page_url = f"{LIST_URL}?rech_page={page}"
            resp = self.http.get(page_url)
            if not resp:
                break
            soup = BeautifulSoup(resp.text, 'lxml')
            found = 0
            # Detail links labelled "Détails" or containing annonce ID
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                text = _clean(a.get_text()).lower()
                if 'détail' in text or 'detail' in text or 'annonce' in href.lower():
                    absolute = urljoin(BASE, href)
                    if absolute not in urls:
                        urls.append(absolute)
                        found += 1
                        if len(urls) >= self.max_listings:
                            break
            if found == 0:
                break
            page += 1
        return urls

    def scrape_listing(self, url: str) -> dict | None:
        resp = self.http.get(url)
        if not resp:
            return None
        try:
            return self._parse(resp.text, url)
        except Exception as exc:
            logger.warning("TunisieAnnonce parse error on %s: %s", url, exc)
            return None

    def _parse(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, 'lxml')

        # Title — usually in <h1> or a prominent td
        title = ''
        for sel in ('h1', '.titre', 'td.titre'):
            el = soup.select_one(sel)
            if el:
                title = _clean(el.get_text())
                break
        if not title:
            # Fallback: find biggest bold text
            for b in soup.find_all(['b', 'strong']):
                t = _clean(b.get_text())
                if len(t) > 20:
                    title = t
                    break

        # Description — collect all paragraph-like td/p text
        description_parts = []
        for el in soup.select('td[class*="desc"], p, .description'):
            t = _clean(el.get_text())
            if len(t) > 40:
                description_parts.append(t)
        description = ' '.join(description_parts[:3])

        # Surface
        surface = _parse_surface('', description + ' ' + title)

        # Price — look for DT/TND near numbers
        price_raw = ''
        price = None
        price_pat = re.compile(r'(\d[\d\s,.]*)\s*(?:DT|TND|dinars?)', re.IGNORECASE)
        for el in soup.find_all(text=price_pat):
            m = price_pat.search(str(el))
            if m:
                price_raw = m.group(0)
                price = _parse_price(price_raw)
                break

        # Location — look for governorate names in text
        TN_GOVS = [
            'Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Zaghouan',
            'Bizerte', 'Beja', 'Jendouba', 'Kef', 'Siliana', 'Sousse',
            'Monastir', 'Mahdia', 'Sfax', 'Kairouan', 'Kasserine',
            'Sidi Bouzid', 'Gabes', 'Medenine', 'Tataouine', 'Gafsa',
            'Tozeur', 'Kebili',
        ]
        governorate = ''
        full_text = soup.get_text()
        for gov in TN_GOVS:
            if gov.lower() in full_text.lower():
                governorate = gov
                break

        # Property type
        combined = (title + ' ' + description + ' ' + url).lower()
        property_type = 'apartment'
        for kw, pt in [
            ('terrain', 'land'), ('villa', 'villa'), ('maison', 'house'),
            ('bureau', 'office'), ('commercial', 'commercial'),
        ]:
            if kw in combined:
                property_type = pt
                break

        transaction_type = 'rent' if any(
            k in combined for k in ['louer', 'location', 'a louer']
        ) else 'sale'

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
            'city': governorate,
            'neighborhood': '',
            'location_raw': governorate,
            'property_type': property_type,
            'transaction_type': transaction_type,
            'bedrooms': None,
            'bathrooms': None,
            'image_url': None,
        }
