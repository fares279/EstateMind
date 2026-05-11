# 🚀 EstateMind Deployment Guide

## Complete Step-by-Step Deployment Instructions

This guide covers deploying EstateMind to production on Render (backend) and Vercel (frontend).

---

## 📋 Prerequisites

### Required Accounts
- ✅ GitHub account with EstateMind repository
- ✅ [Render](https://render.com) account (GitHub-connected)
- ✅ [Vercel](https://vercel.com) account (GitHub-connected)
- ✅ [Stripe](https://stripe.com) account for payments
- ✅ PostgreSQL database (Render provides this)

### Required Information
- GitHub personal access token (for Render)
- Stripe API keys (Secret & Publishable)
- Domain name (optional but recommended)

---

## Part 1: Deploy Backend to Render ⚙️

### Step 1: Create PostgreSQL Database on Render

1. **Go to Render Dashboard**
   - Visit [render.com/dashboard](https://render.com/dashboard)
   - Click **"New +"** button
   - Select **"PostgreSQL"**

2. **Configure Database**
   - **Name**: `estatemind-db`
   - **Database**: `estatemind_db`
   - **User**: `estatemind_user`
   - **Region**: Choose closest to Tunisia (Europe - France recommended)
   - **PostgreSQL Version**: 15 or latest
   - Click **"Create Database"**

3. **Copy Connection Details**
   - Once created, copy the **External Database URL**
   - Format: `postgresql://user:password@host:5432/dbname`
   - Save this for later

### Step 2: Create Web Service for Backend

1. **Create New Service**
   - Click **"New +"** → **"Web Service"**
   - Select your **EstateMind** GitHub repository
   - Connect GitHub account if needed

2. **Configure Build Settings**
   - **Name**: `estatemind-backend`
   - **Region**: Same as database (Europe)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3.11
   - **Build Command**: 
     ```bash
       bash build.sh
     ```
   - **Start Command**:
     ```bash
          gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --log-level debug --access-logfile - --error-logfile -
     ```
    - **Health Check Path**: `/healthz`

3. **Set Environment Variables** (Critical!)
   
   Click **"Advanced"** and add these variables:

   ```
   DEBUG=False
   SECRET_KEY=<generate-strong-key-python-secrets.token_urlsafe(32)>
   ALLOWED_HOSTS=estatemind-backend.onrender.com,yourdomain.com
   
   DB_NAME=estatemind_db
   DB_USER=estatemind_user
   DB_PASSWORD=<from-postgres-creation>
   DB_HOST=<postgres-hostname>
   DB_PORT=5432
   DB_SSLMODE=require
   
   STRIPE_SECRET_KEY=sk_live_<your-stripe-secret>
   STRIPE_PUBLISHABLE_KEY=pk_live_<your-stripe-public>

   CREATE_SUPERUSER=True
   DJANGO_SUPERUSER_USERNAME=admin
   DJANGO_SUPERUSER_EMAIL=admin@example.com
   DJANGO_SUPERUSER_PASSWORD=Admin@12345

   ENABLE_AUTO_SCRAPER=False
   LEGAL_PRELOAD_MODEL=False
   
   CORS_ALLOWED_ORIGINS=https://yourdomain.vercel.app,https://yourdomain.com
   
   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   TIME_ZONE=Africa/Tunis
   ```

4. **Deploy**
   - Click **"Create Web Service"**
   - Wait for build to complete (5-10 minutes)
   - Copy your backend URL: `https://estatemind-backend.onrender.com`

### Step 3: No-Shell Setup

On the free Render plan, Shell is not available. The `backend/build.sh` script runs migrations and collects static files during deploy, and it creates the initial superuser when the environment variables above are present.

Keep `ENABLE_AUTO_SCRAPER=False` and `LEGAL_PRELOAD_MODEL=False` on the Render web service so the worker starts quickly and stays under the free-tier memory cap.

If you need to recreate the admin later, set `CREATE_SUPERUSER=True` again and redeploy.

### Step 4: Verify Backend

```bash
# Test health check
curl https://estatemind-backend.onrender.com/healthz

# View API docs
https://estatemind-backend.onrender.com/api/docs

# Admin panel
https://estatemind-backend.onrender.com/admin
```

---

## Part 2: Deploy Frontend to Vercel ✨

### Step 1: Create Vercel Project

1. **Import GitHub Repository**
   - Go to [vercel.com/import](https://vercel.com/import)
   - Select your **EstateMind** GitHub repository
   - Authorize Vercel with GitHub

2. **Configure Project**
   - **Project Name**: `estatemind-frontend`
   - **Framework**: React
   - **Root Directory**: `frontend`
   - **Build Command**: `CI=false npm run build`
   - **Output Directory**: `build`
   - Click **"Import"**

### Step 2: Set Environment Variables

1. **Go to Project Settings**
   - Click **"Settings"** → **"Environment Variables"**

2. **Add Variables**
   
   During import, set these environment variables:
   ```
   REACT_APP_API_URL=https://estatemind.onrender.com/api
   REACT_APP_STRIPE_PUBLIC_KEY=pk_test_51TT6qSRqB7vJnbZ4lBXfRBC5Qc2LLVFMEkSSsoRdGF3ct2gmdpSr2DIwBgAV3TX6gZvSQn8S6QTZQEnj7eZJNtNI00ruwYsC4j
   ```
   
   If you get validation errors, make sure there are NO extra spaces before/after the URLs.

3. **Deploy**
   - Click **"Deploy"**
   - Wait for build (3-5 minutes)
   - Copy your frontend URL: `https://estatemind-frontend.vercel.app`

### Step 3: Update Backend CORS

1. **Get your Vercel frontend URL**
   - From Vercel dashboard after deployment
   - Format: `https://estatemind.vercel.app`

2. **Go back to Render Backend Service**
   - Dashboard → `estatemind-backend` service → **"Environment"** tab
   - Find `CORS_ALLOWED_ORIGINS` variable
   - Update it to:
     ```
     https://estatemind.vercel.app,localhost:3000
     ```

3. **Save and Redeploy**
   - Click "Save Changes"
   - Render auto-redeploys (~2 minutes)

### Step 4: Verify Frontend

```bash
# Open in browser
https://estatemind-frontend.vercel.app

# Test login
- Email: admin@example.com
- Password: Admin@12345

# Verify features
- Check dark mode toggle
- Test property valuation
- View investment dashboard
```

---

## Part 3: Connect Custom Domain (Optional) 🌐

### Add Domain to Vercel

1. **Go to Vercel Project Settings**
   - Click **"Domains"** in Project Settings
   - Add your custom domain

2. **Update DNS Records**
   - Follow Vercel's DNS configuration
   - Point `yourdomain.com` to Vercel

### Add Domain to Render

1. **Go to Render Service Settings**
   - Click **"Settings"** tab
   - Add custom domain in **"Render Domain"**

---

## Part 4: Setup Production Database ⚡

### Backup Local Data (if needed)

```bash
# Export local SQLite data
cd backend
python manage.py dumpdata > backup.json

# Import to production (via Render Shell)
python manage.py loaddata backup.json
```

### Configure Database Connection Pooling

In Render dashboard for PostgreSQL:
- Enable **"Connection Pooling"** if available
- Set pool size to 10-20

---

## Part 5: Monitor & Maintain 📊

### Check Logs

**Render Backend Logs:**
- Dashboard → Service → **"Logs"** tab
- View real-time logs for errors

**Vercel Frontend Logs:**
- Dashboard → Project → **"Deployments"** → Select deployment → **"Logs"**

### Setup Monitoring

1. **Set Render Alerts**
   - Enable email notifications for crashes
   - Monitor database connections

2. **Monitor Stripe**
   - Check [Stripe Dashboard](https://dashboard.stripe.com) for failed payments
   - Review webhook logs

---

## Part 6: SSL/TLS Certificates 🔒

- ✅ **Render**: Automatically provides SSL
- ✅ **Vercel**: Automatically provides SSL
- Custom domains get SSL automatically

---

## Troubleshooting 🔧

### Backend Won't Deploy

```bash
# Check build command output in Render logs
# Common issues:
- Missing requirements in requirements.txt
- Python version mismatch
- Database connection issues
```

**Solution:**
```bash
# Test locally
python manage.py migrate
python manage.py runserver
```

### Frontend Build Fails

```bash
# Check Vercel build logs
# Common issues:
- Environment variables not set
- Node modules cache issues
- Missing dependencies
```

**Solution:**
```bash
# Clear cache and redeploy
npm cache clean --force
npm install
npm run build
```

### API Calls Return 403 CORS Error

**Solution:**
1. Verify `CORS_ALLOWED_ORIGINS` includes frontend URL
2. Check `ALLOWED_HOSTS` includes backend domain
3. Restart backend service

### Database Connection Errors

**Solution:**
```bash
# Verify credentials
# In Render Shell:
psql -h <host> -U <user> -d <dbname>

# If fails, re-create database
```

---

## Deployment Checklist ✅

- [ ] PostgreSQL database created on Render
- [ ] Backend service deployed to Render
- [ ] Environment variables set on Render
- [ ] Database migrations run
- [ ] Admin user created
- [ ] Static files collected
- [ ] Frontend deployed to Vercel
- [ ] Environment variables set on Vercel
- [ ] CORS properly configured
- [ ] Stripe keys configured
- [ ] API endpoints tested
- [ ] Login/Registration working
- [ ] Payments working
- [ ] Dark mode working
- [ ] Responsive design verified

---

## Production Checklist 🚀

### Security
- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` generated
- [ ] SSL/TLS enabled (automatic)
- [ ] CSRF protection enabled
- [ ] XSS protection enabled
- [ ] SQL injection prevention (Django ORM)

### Performance
- [ ] Database backups configured
- [ ] CDN for static files (Vercel has this)
- [ ] Caching headers configured
- [ ] API rate limiting enabled
- [ ] Database connection pooling

### Monitoring
- [ ] Error logging enabled
- [ ] Email alerts configured
- [ ] Stripe webhook logs monitored
- [ ] Database size monitored

---

## Useful Commands

### Render Shell Commands
```bash
# Run Django commands
python manage.py createsuperuser
python manage.py shell
python manage.py dbshell

# View environment
env | grep DB_

# Restart service
# (Use dashboard - there's a "Restart" button)
```

### Database Management
```bash
# Connect to PostgreSQL
psql -h <host> -U <user> -d <dbname>

# Useful psql commands
\l              # List databases
\dt             # List tables
\du             # List users
\q              # Quit
```

---

## Next Steps

1. ✅ Monitor deployment for 24-48 hours
2. ✅ Test all features in production
3. ✅ Setup monitoring/alerting
4. ✅ Configure backups
5. ✅ Plan scaling strategy

---

**Deployment Status**: Production Ready ✅

For issues, check logs and consult the [README.md](../README.md)
