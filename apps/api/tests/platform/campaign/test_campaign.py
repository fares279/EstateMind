from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.platform.campaign.models import Participant
from estatemind.platform.campaign.views import ParticipantViewSet

SIGNUP = {'full_name': 'Amal Ben Salah', 'email': 'Amal@Example.com', 'phone': '+21622333444', 'region': 'Sfax',
          'role': 'learner', 'motivation': 'I want to understand how property prices move in my region.'}


@mock.patch.object(ParticipantViewSet, '_send_welcome_email')
class CampaignTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_active_participant(self, _email):
        response = self.client.post('/api/campaign/participants/', SIGNUP, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        participant = Participant.objects.get()
        self.assertEqual(participant.email, 'amal@example.com')
        self.assertTrue(participant.is_active)

    def test_signup_cannot_set_inactive_flag(self, _email):
        self.client.post('/api/campaign/participants/', {**SIGNUP, 'is_active': False}, format='json')
        self.assertTrue(Participant.objects.get().is_active)

    def test_duplicate_email_and_short_motivation_are_rejected(self, _email):
        self.client.post('/api/campaign/participants/', SIGNUP, format='json')
        again = self.client.post('/api/campaign/participants/', {**SIGNUP, 'email': 'amal@example.com'}, format='json')
        self.assertEqual(again.status_code, 400)
        short = self.client.post('/api/campaign/participants/', {**SIGNUP, 'email': 'b@example.com', 'motivation': 'hi'},
                                 format='json')
        self.assertEqual(short.status_code, 400)

    def test_participant_list_is_not_public(self, _email):
        self.client.post('/api/campaign/participants/', SIGNUP, format='json')
        response = self.client.get('/api/campaign/participants/')
        self.assertEqual(response.status_code, 405)
        self.assertNotIn(b'amal@example.com', response.content)

    def test_stats_count_by_role(self, _email):
        self.client.post('/api/campaign/participants/', SIGNUP, format='json')
        self.client.post('/api/campaign/participants/', {**SIGNUP, 'email': 'c@example.com', 'role': 'volunteer'},
                         format='json')
        stats = self.client.get('/api/campaign/stats/').json()
        self.assertEqual((stats['total_participants'], stats['learners'], stats['volunteers']), (2, 1, 1))
