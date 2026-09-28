from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.assistants.chatbot.models import ChatbotResponseLog, ChatbotSession

CONTRACT = {'session_id', 'message', 'intent', 'confidence', 'sources', 'quality_label', 'grounded',
            'turn_index', 'response_log_id'}


class ChatbotConversationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _say(self, message, session_id=None):
        body = {'message': message, **({'session_id': session_id} if session_id else {})}
        response = self.client.post('/api/chatbot/message/', body, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_empty_message_is_rejected(self):
        self.assertEqual(self.client.post('/api/chatbot/message/', {'message': '  '}, format='json').status_code, 400)

    def test_response_contract_and_logging(self):
        reply = self._say('Hello')
        self.assertTrue(CONTRACT <= set(reply), CONTRACT - set(reply))
        self.assertEqual(reply['turn_index'], 0)
        self.assertTrue(reply['message'])
        self.assertTrue(ChatbotResponseLog.objects.filter(id=reply['response_log_id']).exists())

    def test_session_memory_across_turns(self):
        first = self._say('My name is Sami')
        second = self._say('What is my name?', first['session_id'])
        self.assertEqual(second['session_id'], first['session_id'])
        self.assertEqual(second['turn_index'], 1)
        self.assertIn('Sami', second['message'])
        session = self.client.get('/api/chatbot/session/', {'session_id': first['session_id']}).json()
        self.assertEqual(session['turn_count'], 2)

    def test_long_messages_are_truncated_not_rejected(self):
        self.assertTrue(self._say('prix ' * 400)['message'])

    def test_unknown_session_returns_404(self):
        self.assertEqual(self.client.get('/api/chatbot/session/', {'session_id': 'nope'}).status_code, 404)


class ChatbotFeedbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reply = self.client.post('/api/chatbot/message/', {'message': 'Hello'}, format='json').json()

    def test_feedback_by_session_and_turn(self):
        response = self.client.post('/api/chatbot/feedback/', {
            'session_id': self.reply['session_id'], 'turn_index': self.reply['turn_index'], 'feedback': 'thumbs_up'},
            format='json')
        self.assertEqual(response.status_code, 200, response.content)
        log = ChatbotResponseLog.objects.get(id=self.reply['response_log_id'])
        self.assertEqual(log.user_feedback, 'thumbs_up')

    def test_invalid_feedback_value(self):
        response = self.client.post('/api/chatbot/feedback/', {
            'response_log_id': self.reply['response_log_id'], 'feedback': 'meh'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_unknown_response_log(self):
        response = self.client.post('/api/chatbot/feedback/', {
            'response_log_id': 99999, 'session_id': self.reply['session_id'], 'feedback': 'thumbs_up'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ChatbotSession.objects.exists())

    def test_feedback_by_id_needs_the_matching_session(self):
        url, log_id = '/api/chatbot/feedback/', self.reply['response_log_id']
        self.assertEqual(self.client.post(url, {'response_log_id': log_id, 'feedback': 'thumbs_down'},
                                          format='json').status_code, 400)
        other = self.client.post('/api/chatbot/message/', {'message': 'Hello'}, format='json').json()['session_id']
        self.assertEqual(self.client.post(url, {'response_log_id': log_id, 'session_id': other,
                                                'feedback': 'thumbs_down'}, format='json').status_code, 404)
        ok = self.client.post(url, {'response_log_id': log_id, 'session_id': self.reply['session_id'],
                                    'feedback': 'thumbs_down'}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ChatbotResponseLog.objects.get(id=log_id).user_feedback, 'thumbs_down')
