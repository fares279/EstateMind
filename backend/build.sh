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
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
  User.objects.create_superuser('$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD', full_name='Admin', role='admin', is_email_verified=True)
    print('Superuser created successfully.')
else:
    print('Superuser already exists.')
END
fi
