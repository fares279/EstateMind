import re

from django.test import SimpleTestCase

from estatemind.assistants.legal.services import dataset_service as ds


class OfficialTextTests(SimpleTestCase):
    def test_glyph_name_extraction_is_detected(self):
        # pypdf returns glyph names for some Arabic PDFs; a stray control character in this
        # pattern once let 14 such passages into the index
        raw = 'jeemmedial/seenmedial/lamisolated/alefisolated /yehfinal/dadmedial/aleffinal/qafinitial'
        self.assertGreaterEqual(len(ds._GLYPH_NAMES.findall(raw)), 8)

    def test_unreadable_official_texts_are_not_indexed(self):
        for chunk in ds.load_official_texts(80, 20):
            self.assertIsNone(re.search(r'[a-z]+(?:isolated|initial|medial|final)/', chunk['text']), chunk['metadata']['law_name'])
