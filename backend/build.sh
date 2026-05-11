#!/bin/bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py makemigrations
python manage.py migrate

# If a fixture export exists in the repo, attempt to load it to populate the DB.
# Try to load a fixture export from either the repo root or backend/fixtures
if [ -f "$(pwd)/../fulldump.json" ]; then
  FIXTURE_PATH="$(pwd)/../fulldump.json"
elif [ -f "$(pwd)/fixtures/fulldump.json" ]; then
  FIXTURE_PATH="$(pwd)/fixtures/fulldump.json"
else
  FIXTURE_PATH=""
fi

if [ -n "$FIXTURE_PATH" ]; then
  echo "=== Fixture: Loading $FIXTURE_PATH into the database ==="
  python manage.py loaddata "$FIXTURE_PATH" || echo "WARNING: loaddata reported errors; continuing deploy"
fi

# Bootstrap superuser if CREATE_SUPERUSER=True
echo "=== Bootstrap: Checking CREATE_SUPERUSER env var: $CREATE_SUPERUSER ==="
if [ "$CREATE_SUPERUSER" = "True" ]; then
  echo "=== Bootstrap: Starting superuser creation/update ==="
  python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
print("DEBUG: Looking for user with email=$DJANGO_SUPERUSER_EMAIL")
user, created = User.objects.get_or_create(
    email='$DJANGO_SUPERUSER_EMAIL',
    defaults={
        'full_name': 'Admin',
        'role': 'admin',
        'is_email_verified': True,
    },
)
print(f"DEBUG: User found/created: {user.email}, created={created}")
user.is_staff = True
user.is_superuser = True
user.role = 'admin'
user.is_email_verified = True
user.set_password('$DJANGO_SUPERUSER_PASSWORD')
user.save()
print('SUCCESS: Superuser %s successfully.' % ('created' if created else 'updated'))
END
  echo "=== Bootstrap: Superuser creation completed ==="
else
  echo "=== Bootstrap: CREATE_SUPERUSER not True, skipping superuser setup ==="
fi
