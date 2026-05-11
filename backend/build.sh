#!/bin/bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Bootstrap superuser if CREATE_SUPERUSER=True
if [ "$CREATE_SUPERUSER" = "True" ]; then
  python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
user, created = User.objects.get_or_create(
    email='$DJANGO_SUPERUSER_EMAIL',
    defaults={
        'full_name': 'Admin',
        'role': 'admin',
        'is_email_verified': True,
    },
)
user.is_staff = True
user.is_superuser = True
user.role = 'admin'
user.is_email_verified = True
user.set_password('$DJANGO_SUPERUSER_PASSWORD')
user.save()
print('Superuser %s successfully.' % ('created' if created else 'updated'))
