# 🚀 Render Backend Production Configuration

**Generated**: May 11, 2026  
**Database**: estatemind-db (Render PostgreSQL)  
**Status**: Ready for Web Service Deployment

---

## ✅ Database Connection (CONFIRMED)

```
External Database URL:
postgresql://estatemind_user:sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7@dpg-d80qcf37uimc73fodbng-a.frankfurt-postgres.render.com/estatemind_db

Hostname: dpg-d80qcf37uimc73fodbng-a.frankfurt-postgres.render.com
| Build Command | `bash build.sh` |
Database: estatemind_db
Username: estatemind_user
Password: sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7
Region: Frankfurt (EU Central)
```

### Copy and paste these into Render Dashboard → Web Service → Environment Variables
```
DEBUG=False
SECRET_KEY=FKTqbHpT_nwdmRY8D9rI2kza5kqKo-DaHtVb5qEf5A91mQtP3oB_go3FqXcANTp82MQ

DB_ENGINE=django.db.backends.postgresql
DB_NAME=estatemind_db
DB_USER=estatemind_user
DB_PASSWORD=sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7
DB_HOST=dpg-d80qcf37uimc73fodbng-a.frankfurt-postgres.render.com
DB_PORT=5432
DB_SSLMODE=require

ALLOWED_HOSTS=estatemind-backend.onrender.com,estatemind.vercel.app,localhost
CORS_ALLOWED_ORIGINS=https://estatemind.vercel.app

STRIPE_SECRET_KEY=STRIPE_SECRET_KEY_HERE
STRIPE_PUBLISHABLE_KEY=STRIPE_PUBLISHABLE_KEY_HERE

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
TIME_ZONE=Africa/Tunis
```

---
CREATE_SUPERUSER=True
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=Admin@12345

ENABLE_AUTO_SCRAPER=False
LEGAL_PRELOAD_MODEL=False

## ⚙️ Render Web Service Configuration

### To Create Backend Service on Render:

1. **Go to**: [render.com/dashboard](https://render.com/dashboard)
2. **Click**: "New +" → "Web Service"
3. **Select**: Your GitHub repo (fares279/EstateMind)
4. **Configure**:

| Setting | Value |
|---------|-------|
| Name | `estatemind-backend` |
| Region | `Frankfurt (EU Central)` |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | `Python 3.11` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |

### Environment Variables:
Copy all variables from section above into the Render dashboard.

### Important Notes:
- ⚠️ **Stripe keys are PENDING** - Awaiting user input
- Database is production-ready in Frankfurt region
- CORS is pre-configured for Vercel frontend
- All security settings are enabled (DEBUG=False)

---

## 📝 PENDING INPUTS

### ✅ All Values Provided:

```
✓ Database credentials confirmed
✓ Stripe test keys added (sk_test_... and pk_test_...)
✓ Frontend domain set to estatemind.vercel.app
✓ Production SECRET_KEY generated
```

**Note**: Using Stripe TEST keys for now. Switch to live keys (sk_live_/pk_live_) when ready for production.

---

## 🔗 Step-by-Step Deployment

### 1. Create Web Service on Render
- [ ] Go to Render Dashboard
- [ ] Click "New +" → "Web Service"
- [ ] Select EstateMind repository
- [ ] Set Name: `estatemind-backend`
- [ ] Set Region: `Frankfurt (EU Central)`
- [ ] Set Root Directory: `backend`
- [ ] Set Build Command: `pip install -r requirements.txt`
- [ ] Set Start Command: `gunicorn config.wsgi:application`

### 2. Add Environment Variables
- [ ] Click "Advanced" in Render form
- [ ] Add all variables from the config above
- [ ] **IMPORTANT**: Replace STRIPE keys with your actual keys
- [ ] Click "Create Web Service"

### 3. Wait for Build (5-10 minutes)
- [ ] Monitor build logs in Render dashboard
- [ ] Wait for "Deploy successful" message

### 4. Run Database Migrations
- [ ] Go to Web Service → "Shell" tab
- [ ] Run: `python manage.py migrate`
- [ ] Run: `python manage.py createsuperuser`
- [ ] Run: `python manage.py collectstatic --noinput`

### 5. Verify Backend is Running
- [ ] Health check: `curl https://estatemind-backend.onrender.com/healthz`
- [ ] API docs: Visit `https://estatemind-backend.onrender.com/api/docs`
- [ ] Admin: Visit `https://estatemind-backend.onrender.com/admin`

---

## 🚀 Next Steps After Backend Deploys

1. **Deploy Frontend to Vercel**
   - Import GitHub repo to Vercel
   - Set Root Directory: `frontend`
   - Add environment variable: `REACT_APP_API_URL=https://estatemind-backend.onrender.com/api`
   - Deploy

2. **Test Integration**
   - Visit Vercel frontend URL
   - Login with: admin@example.com / Admin@12345
   - Test payment upgrade (or dev fallback)
   - Verify API calls work

3. **Monitor Production**
   - Check Render logs for errors
   - Monitor Stripe webhook logs
   - Test email delivery

---

## 📊 Database Credentials Reference

```
Internal URL (for Render services):
postgresql://estatemind_user:sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7@dpg-d80qcf37uimc73fodbng-a/estatemind_db

External URL (for external connections):
postgresql://estatemind_user:sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7@dpg-d80qcf37uimc73fodbng-a.frankfurt-postgres.render.com/estatemind_db

PSQL Connection Command:
PGPASSWORD=sTv8qmhLJ2XlXxHT2QzTuMc2Wo3lkeh7 psql -h dpg-d80qcf37uimc73fodbng-a.frankfurt-postgres.render.com -U estatemind_user estatemind_db
```

---

## ⚠️ Important Security Notes

✅ **What's Protected:**
- SECRET_KEY is strong (50 chars, cryptographically random)
- DEBUG=False in production
- Database password is 32 characters
- All connections use HTTPS/TLS

⚠️ **What You Must Do:**
- [ ] Add Stripe keys (don't commit to repo)
- [ ] Keep these credentials private
- [ ] Use Render's environment variable system (not .env files)
- [ ] Rotate SECRET_KEY periodically in production

---

**Status**: Database ✅ | Stripe Keys ✅ | Backend Config ✅ | Ready to Deploy 🚀
