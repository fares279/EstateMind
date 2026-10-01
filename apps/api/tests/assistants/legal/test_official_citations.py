import json
from unittest import mock

from django.test import SimpleTestCase

from estatemind.assistants.legal.services import dataset_service as ds
from estatemind.assistants.legal.services.retrieval_quality import gold_match

CODE = ('Loi n° 1 portant promulgation. Article 1 Texte de la loi. ANNEXES liste. '
        + ' '.join(f'Article {n} ' + 'mot ' * 30 for n in range(10, 16))
        + 'ANNEXES • Autre loi Article 99 ne doit pas apparaître')


class SpanTests(SimpleTestCase):
    def test_only_the_verified_part_is_kept(self):
        part = ds._span(CODE, {'start': 'Article 10', 'end': 'ANNEXES •'})
        self.assertTrue(part.startswith('Article 10'))
        self.assertNotIn('Article 99', part)

    def test_missing_marker_skips_the_text(self):
        self.assertIsNone(ds._span(CODE, {'start': 'Article 500', 'end': 'ANNEXES •'}))
        self.assertIsNone(ds._span(CODE, {'start': 'Article 10', 'end': 'no such end'}))


class CitationTests(SimpleTestCase):
    def _chunks(self):
        info = {'code': {'title': 'Code test', 'source_url': 'u', 'cite_articles': True,
                         'span': {'start': 'Article 10', 'end': 'ANNEXES •'}}}
        with mock.patch.object(ds, '_official_text', return_value=CODE), \
                mock.patch('pathlib.Path.exists', return_value=True), \
                mock.patch('pathlib.Path.read_text', return_value=json.dumps(info)):
            return ds.load_official_texts(40, 10)

    def test_passages_cite_the_articles_they_cover(self):
        chunks = self._chunks()
        refs = [c['metadata']['article_ref'] for c in chunks]
        self.assertEqual(refs[0], 'Code test, art. 10 à 11')  # 40 words reach the next heading
        # a passage that starts inside article N and reaches N+1 cites both
        self.assertTrue(any(' à ' in r for r in refs), refs)
        for c in chunks:
            first_heading = c['text'].split('Article ')[1].split()[0] if 'Article ' in c['text'] else None
            if first_heading and not c['text'].startswith('Article'):
                start = int(c['metadata']['article_ref'].split('art. ')[1].split()[0])
                self.assertLess(start, int(first_heading))  # starts in the previous article

    def test_gold_matches_article_ranges(self):
        meta = {'law_name': 'Code test', 'article_ref': 'Code test, art. 67 à 69', 'article_index': -1}
        self.assertTrue(gold_match(meta, ['Code test:68']))
        self.assertFalse(gold_match(meta, ['Code test:70']))
        self.assertFalse(gold_match(meta, ['Autre code:68']))
        self.assertTrue(gold_match({'article_index': 13}, [13]))
        self.assertTrue(gold_match({'law_name': 'C', 'article_ref': 'C, art. 377 ter', 'article_index': -1}, ['C:377']))
