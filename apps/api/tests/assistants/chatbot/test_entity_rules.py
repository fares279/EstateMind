from django.test import SimpleTestCase, TestCase

from estatemind.assistants.chatbot.services import intent_classifier as ic
from estatemind.market.core.models import Delegation, Region


def _extract(message):
    classifier = ic.IntentClassifier.__new__(ic.IntentClassifier)  # no embedding model needed
    return classifier._extract_entities(message)


class GreetingRuleTests(SimpleTestCase):
    def test_greetings(self):
        for message in ('Hello', 'hi!', 'Bonjour', 'Thanks a lot', 'My name is Sami', 'salam'):
            self.assertTrue(ic.is_greeting(message), message)

    def test_questions_containing_greeting_letters_are_not_greetings(self):
        for message in ('Which delegations will grow fastest?', 'Is this a high yield area?',
                        'Should I buy in Chebba?', 'this price seems high'):
            self.assertFalse(ic.is_greeting(message), message)

    def test_greeting_with_a_real_question_is_not_a_greeting(self):
        self.assertFalse(ic.is_greeting('Hi, what are apartment prices in Sousse?'))
        self.assertFalse(ic.is_greeting('Hello, will prices rise next year?'))


class LocationExtractionTests(TestCase):
    def setUp(self):
        tunis = Region.objects.create(governorate='Tunis')
        nabeul = Region.objects.create(governorate='Nabeul')
        Delegation.objects.create(region=tunis, name='La Marsa')
        Delegation.objects.create(region=nabeul, name='Hammamet')
        Delegation.objects.create(region=nabeul, name='Béni Khiar')

    def test_tunisia_is_not_tunis(self):
        self.assertNotIn('location', _extract('What is the average price in Tunisia?'))

    def test_governorate_and_delegation_names(self):
        self.assertEqual(_extract('prices in Tunis please')['location'], 'Tunis')
        self.assertEqual(_extract('Is la marsa expensive?')['location'], 'La Marsa')

    def test_accents_and_case_do_not_matter(self):
        self.assertEqual(_extract('flats in BENI KHIAR')['location'], 'Béni Khiar')

    def test_delegation_wins_over_its_governorate(self):
        entities = _extract('Hammamet or elsewhere in Nabeul?')
        self.assertEqual((entities['location'], entities['location_type']), ('Hammamet', 'delegation'))

    def test_places_missing_from_the_database_come_from_the_reference_list(self):
        # Sfax is not in this test database; the delegations reference file has it
        entities = _extract('What about Sfax?')
        self.assertEqual(entities['location_type'], 'governorate')
        self.assertEqual(entities['location'].lower(), 'sfax')
