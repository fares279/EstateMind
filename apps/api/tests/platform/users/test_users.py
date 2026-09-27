from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class AccountAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='owner@example.com', password='pw12345!x', full_name='Owner')

    def test_anonymous_cannot_list_or_read_accounts(self):
        # /api/auth/ is only the router's empty index now
        self.assertNotIn(b'owner@example.com', self.client.get('/api/auth/').content)
        self.assertEqual(self.client.get(f'/api/auth/{self.user.id}/').status_code, 404)

    def test_anonymous_cannot_edit_create_or_delete_accounts(self):
        self.client.patch(f'/api/auth/{self.user.id}/', {'plan': 'investor'}, format='json')
        self.client.post('/api/auth/', {'email': 'x@example.com', 'password': 'a'}, format='json')
        self.client.delete(f'/api/auth/{self.user.id}/')
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, 'free')
        self.assertFalse(User.objects.filter(email='x@example.com').exists())

    def test_profile_update_cannot_change_plan_role_or_email(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch('/api/auth/update_profile/', {
            'full_name': 'New Name', 'phone': '+21612345678',
            'plan': 'investor', 'plan_expires_at': '2099-01-01T00:00:00Z', 'role': 'admin', 'email': 'other@example.com',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.phone), ('New Name', '+21612345678'))
        self.assertEqual((self.user.plan, self.user.role, self.user.email), ('free', 'viewer', 'owner@example.com'))
        self.assertIsNone(self.user.plan_expires_at)

    def test_me_requires_login(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/auth/me/').json()['email'], 'owner@example.com')


class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_requires_otp_before_verified(self):
        response = self.client.post('/api/auth/register/', {
            'email': 'new@example.com', 'password': 'Str0ng!Passw0rd', 'password2': 'Str0ng!Passw0rd',
            'password_confirm': 'Str0ng!Passw0rd', 'full_name': 'New User'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['otp_required'])
        self.assertFalse(User.objects.get(email='new@example.com').is_email_verified)

    def test_token_obtain_and_refresh(self):
        User.objects.create_user(email='login@example.com', password='pw12345!x', full_name='Login',
                                 is_email_verified=True)
        response = self.client.post('/api/auth/token/', {'email': 'login@example.com', 'password': 'pw12345!x'})
        self.assertEqual(response.status_code, 200, response.content)
        tokens = response.json()
        self.assertIn('access', tokens)
        refreshed = self.client.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']})
        self.assertEqual(refreshed.status_code, 200)

    def test_wrong_password_is_rejected(self):
        User.objects.create_user(email='login@example.com', password='pw12345!x', full_name='Login')
        response = self.client.post('/api/auth/token/', {'email': 'login@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
