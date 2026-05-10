# EstateMind 🏢

**AI-Powered Real Estate Intelligence Platform for Tunisia**

A comprehensive full-stack application that leverages artificial intelligence, machine learning, and advanced data analytics to provide intelligent real estate solutions including property valuation, market analysis, legal compliance, investment opportunities, and climate risk assessment.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Running Locally](#running-locally)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Database Setup](#database-setup)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Project Overview

**EstateMind** is a sophisticated real estate platform designed specifically for the Tunisian market. It integrates multiple intelligent modules to help users, investors, and real estate professionals make data-driven decisions.

### Core Modules:

1. **Property Valuation** - AI-powered price estimation using machine learning models (CatBoost, XGBoost)
2. **Market Analysis** - Comprehensive market trends, price forecasting, and comparative analysis
3. **Legal & Compliance** - AI-powered legal document analysis and compliance checking using ChromaDB RAG
4. **Investment Portfolio** - Track and analyze real estate investments with risk assessment
5. **Climate Risk Intelligence** - Climate impact analysis and risk scoring for properties
6. **Multi-Agent Simulation** - Market dynamics simulation using Mesa framework
7. **Community Campaigns** - Crowdfunding and community-based real estate projects
8. **AI Chat Assistant** - Natural language interface for property queries
9. **Professional Account Management** - Tiered subscription system (Basic/Pro/Premium)

---

## ✨ Key Features

### User Features
- 🔐 **Authentication System** - JWT-based secure authentication with OTP verification
- 🏠 **Property Discovery** - Advanced search and filtering with map integration
- 💰 **Smart Valuation** - Real-time property price estimation
- 📊 **Investment Analytics** - Portfolio tracking and performance analytics
- 📋 **Legal AI Assistant** - Document analysis and compliance checking
- 🌍 **Climate Risk Assessment** - Environmental impact analysis
- 💳 **Stripe Payments** - Secure subscription management and billing
- 🤖 **AI Chat Interface** - Interactive property search and recommendations

### Professional Features
- 📈 **Advanced Analytics Dashboard** - Real-time market insights
- 🔌 **API Access** - Professional API keys with scoped permissions
- 🚨 **Custom Alerts** - Price alerts and market notifications
- 👥 **Multi-User Management** - Team collaboration features
- 📱 **Mobile-Optimized** - Fully responsive design
- 🎨 **Dark Mode Support** - Modern UI with theme switching

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Django 4.2.10 with Django REST Framework
- **Database**: PostgreSQL (primary) / SQLite (local dev)
- **Authentication**: JWT with SimplJWT, Token Blacklist
- **AI/ML**:
  - CatBoost for price prediction
  - XGBoost for market analysis
  - Sentence Transformers for embeddings
  - ChromaDB for RAG (Legal AI)
  - Mesa for multi-agent simulation
  - PyTorch for deep learning tasks
- **Payment**: Stripe integration
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Server**: Gunicorn + WhiteNoise for static files
- **CORS**: django-cors-headers
- **Deployment**: Docker, Render, PostgreSQL

### Frontend
- **Framework**: React 18.3.1 with React Router v6
- **Styling**: Tailwind CSS with custom components
- **UI Components**: Lucide React icons, Framer Motion animations
- **Charts**: Recharts for data visualization
- **Maps**: Leaflet.js for interactive maps
- **HTTP**: Axios with JWT interceptors
- **Payment**: Stripe React SDK
- **Deployment**: Vercel (serverless)

### DevOps & Deployment
- **Backend**: Render (PostgreSQL + Gunicorn)
- **Frontend**: Vercel (Next.js compatible)
- **Version Control**: Git/GitHub
- **API Documentation**: Swagger UI (auto-generated)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (React 18)                    │
│  Vercel Deployment (SPA with routing & state management) │
│                                                          │
│ ┌────────┬──────────┬──────────┬────────────┬─────────┐ │
│ │ Auth   │ Explore  │ Valuation│ Investment │ Account │ │
│ │ Pages  │ Market   │  AI      │ Dashboard  │ Settings│ │
│ └────────┴──────────┴──────────┴────────────┴─────────┘ │
│                          ▼                               │
│              Axios HTTP Client (JWT auth)                │
└─────────────────────────────────────────────────────────┘
                         │
                  REST API Gateway
                         │
┌─────────────────────────────────────────────────────────┐
│              Backend (Django 4.2 + DRF)                  │
│  Render Deployment (Gunicorn + PostgreSQL Connection)   │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │           API Layer (REST Endpoints)                │ │
│ │  • /api/auth/        (JWT authentication)           │ │
│ │  • /api/core/        (Properties & listings)        │ │
│ │  • /api/features/    (Search & filtering)           │ │
│ │  • /api/valuation/   (Price prediction)             │ │
│ │  • /api/forecast/    (Market analysis)              │ │
│ │  • /api/legal/       (Document analysis RAG)        │ │
│ │  • /api/investor/    (Portfolio management)         │ │
│ │  • /api/campaign/    (Community projects)           │ │
│ │  • /api/simulation/  (Market simulation)            │ │
│ │  • /api/billing/     (Stripe payments)              │ │
│ │  • /api/scraper/     (Data collection)              │ │
│ │  • /api/chatbot/     (AI assistant)                 │ │
│ └─────────────────────────────────────────────────────┘ │
│                         ▼                               │
│ ┌─────────────────────────────────────────────────────┐ │
│ │          ML/AI Services Layer                       │ │
│ │  • CatBoost/XGBoost Models (valuation)             │ │
│ │  • Sentence Transformers (embeddings)             │ │
│ │  • ChromaDB Vector Store (legal RAG)              │ │
│ │  • Mesa Multi-Agent Simulation                    │ │
│ │  • PyTorch Models (deep learning)                 │ │
│ └─────────────────────────────────────────────────────┘ │
│                         ▼                               │
│ ┌─────────────────────────────────────────────────────┐ │
│ │       Database & External Services                 │ │
│ │  • PostgreSQL (primary data store)                 │ │
│ │  • Stripe (payment processing)                    │ │
│ │  • External data sources (scraper)                │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
EstateMind/
├── backend/                          # Django Backend
│   ├── manage.py                     # Django CLI
│   ├── requirements.txt              # Python dependencies
│   ├── Procfile                      # Render deployment config
│   ├── runtime.txt                   # Python version
│   │
│   ├── config/                       # Django settings & URLs
│   │   ├── settings.py               # Global configuration
│   │   ├── urls.py                   # URL routing
│   │   ├── wsgi.py                   # WSGI application
│   │   └── admin_site.py             # Admin customization
│   │
│   ├── core/                         # Core property models
│   │   ├── models.py                 # Property, Listing models
│   │   ├── views.py                  # Core API endpoints
│   │   ├── serializers.py            # API serializers
│   │   └── urls.py                   # Core routes
│   │
│   ├── users/                        # Authentication & User management
│   │   ├── models.py                 # Custom User model
│   │   ├── views.py                  # Auth endpoints (login, register, JWT)
│   │   ├── serializers.py            # User serializers
│   │   └── urls.py                   # Auth routes
│   │
│   ├── valuation/                    # Property Valuation Module
│   │   ├── models.py                 # Valuation models
│   │   ├── views.py                  # Valuation API
│   │   ├── ml_models.py              # CatBoost/XGBoost models
│   │   └── urls.py
│   │
│   ├── forecast/                     # Market Forecasting
│   │   ├── models.py                 # Forecast models
│   │   ├── views.py                  # Forecast API
│   │   └── urls.py
│   │
│   ├── legal/                        # Legal AI Assistant (RAG)
│   │   ├── models.py                 # Legal documents
│   │   ├── views.py                  # Legal API
│   │   ├── rag_engine.py             # ChromaDB integration
│   │   └── urls.py
│   │
│   ├── investor/                     # Investment Management
│   │   ├── models.py                 # Portfolio, risk models
│   │   ├── views.py                  # Investor API
│   │   └── urls.py
│   │
│   ├── campaign/                     # Community Campaigns
│   │   ├── models.py                 # Campaign models
│   │   ├── views.py                  # Campaign API
│   │   └── urls.py
│   │
│   ├── simulation/                   # Multi-Agent Simulation
│   │   ├── models.py                 # Simulation data
│   │   ├── agents.py                 # Mesa agents
│   │   ├── views.py                  # Simulation API
│   │   └── urls.py
│   │
│   ├── scraper/                      # Data Collection
│   │   ├── models.py                 # Scraping tasks
│   │   ├── tasks.py                  # Scraper jobs
│   │   └── urls.py
│   │
│   ├── billing/                      # Payment Management
│   │   ├── models.py                 # Payment, Subscription models
│   │   ├── views.py                  # Stripe integration endpoints
│   │   ├── serializers.py            # Payment serializers
│   │   └── urls.py
│   │
│   ├── chatbot/                      # AI Chat Assistant
│   │   ├── models.py                 # Chat history
│   │   ├── views.py                  # Chat API
│   │   └── urls.py
│   │
│   ├── features/                     # Search & Filtering
│   │   ├── models.py                 # Filter configs
│   │   ├── views.py                  # Search API
│   │   └── urls.py
│   │
│   └── db.sqlite3                    # Local SQLite database
│
├── frontend/                         # React Frontend
│   ├── package.json                  # Dependencies & scripts
│   ├── public/
│   │   └── index.html                # Main HTML entry
│   │
│   ├── src/
│   │   ├── index.js                  # React entry point
│   │   ├── App.js                    # Main app component
│   │   ├── index.css                 # Global styles
│   │   │
│   │   ├── context/
│   │   │   ├── AuthContext.jsx       # JWT & auth state
│   │   │   └── ThemeContext.jsx      # Dark mode
│   │   │
│   │   ├── services/
│   │   │   ├── api.js                # Axios client with JWT
│   │   │   ├── mapService.js         # Leaflet maps
│   │   │   └── stripeService.js      # Stripe integration
│   │   │
│   │   ├── components/
│   │   │   ├── Navigation/
│   │   │   │   ├── Topbar.jsx
│   │   │   │   └── Footer.jsx
│   │   │   ├── auth/
│   │   │   │   ├── LoginForm.jsx
│   │   │   │   ├── RegisterForm.jsx
│   │   │   │   └── ProtectedRoute.jsx
│   │   │   ├── PropertyCard.jsx      # Property display
│   │   │   ├── SearchFilters.jsx     # Advanced search
│   │   │   ├── PaymentModal.jsx      # Stripe checkout
│   │   │   ├── AIChatWidget.jsx      # Chat interface
│   │   │   └── Dashboard/            # Dashboard components
│   │   │
│   │   ├── pages/
│   │   │   ├── HomePage.jsx          # Landing page
│   │   │   ├── ExplorePage.jsx       # Property exploration
│   │   │   ├── ValuatePage.jsx       # Valuation tool
│   │   │   ├── LegalAIPage.jsx       # Legal assistant
│   │   │   ├── AnalyzePage.jsx       # Market analysis
│   │   │   ├── SimulatePage.jsx      # Market simulation
│   │   │   ├── CommunityCampaignPage.jsx
│   │   │   ├── invest/
│   │   │   │   ├── InvestLayout.jsx
│   │   │   │   ├── InvestDashboard.jsx
│   │   │   │   ├── PortfolioPage.jsx
│   │   │   │   ├── ScannerPage.jsx
│   │   │   │   ├── OpportunitiesPage.jsx
│   │   │   │   └── RiskPage.jsx
│   │   │   ├── account/
│   │   │   │   ├── AccountDashboardPage.jsx
│   │   │   │   ├── AccountSettingsPage.jsx
│   │   │   │   ├── AccountApiKeysPage.jsx
│   │   │   │   └── AccountAlertsPage.jsx
│   │   │   ├── auth/
│   │   │   │   ├── LoginPage.jsx
│   │   │   │   ├── RegisterPage.jsx
│   │   │   │   ├── VerifyOTPPage.jsx
│   │   │   │   ├── ForgotPasswordPage.jsx
│   │   │   │   └── ResetPasswordPage.jsx
│   │   │   └── NotFoundPage.jsx
│   │   │
│   │   └── styles/
│   │       └── tailwind.css          # Tailwind configuration
│   │
│   ├── tailwind.config.js            # Tailwind customization
│   ├── postcss.config.js             # PostCSS configuration
│   ├── .env                          # Frontend env vars
│   └── .env.example                  # Environment template
│
├── .env                              # Root environment file
├── .env.example                      # Environment template
├── .gitignore                        # Git ignore rules
├── README.md                         # This file
└── LICENSE                           # Project license
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** 16+ and npm/yarn
- **Python** 3.10+
- **PostgreSQL** 12+ (for production)
- **Git**
- **Stripe Account** (for payment processing)

### Quick Start

#### 1. Clone the Repository

```bash
git clone https://github.com/fares279/EstateMind.git
cd EstateMind
```

#### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration
```

#### 3. Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
# Edit .env with your backend URL
```

---

## 🔐 Environment Configuration

### Backend `.env` Template

```env
# Django Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True  # Set to False in production
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database (PostgreSQL)
DB_ENGINE=postgresql
DB_NAME=estatemind_db
DB_USER=estatemind_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432

# Use SQLite for local development (optional)
USE_SQLITE=False

# JWT Settings
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Stripe API Keys
STRIPE_SECRET_KEY=sk_live_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_publishable_key

# Email Configuration (for OTP, password reset)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# TIME ZONE
TIME_ZONE=Africa/Tunis

# ML Model Paths
VALUATION_MODEL_PATH=models/valuation_model.pkl
FORECAST_MODEL_PATH=models/forecast_model.pkl
```

### Frontend `.env` Template

```env
# API Configuration
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_API_BASE_URL=http://localhost:8000

# Stripe Public Key
REACT_APP_STRIPE_PUBLIC_KEY=pk_test_your_public_key

# Chat API (if separate)
REACT_APP_CHAT_API_URL=http://localhost:8000/api/chatbot

# Map Configuration
REACT_APP_MAP_CENTER_LAT=36.8065
REACT_APP_MAP_CENTER_LNG=10.1686
REACT_APP_DEFAULT_ZOOM=10

# Feature Flags
REACT_APP_ENABLE_DARK_MODE=true
REACT_APP_ENABLE_CHAT=true
REACT_APP_ENABLE_VALUATION=true
```

---

## 🏃 Running Locally

### Start Backend

```bash
cd backend

# Apply migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (admin account)
python manage.py createsuperuser

# Load sample data (if available)
python manage.py loaddata fixtures/sample_data.json

# Start development server
python manage.py runserver
```

Backend will be available at: `http://localhost:8000`

Admin panel: `http://localhost:8000/admin`

API Docs: `http://localhost:8000/api/docs`

### Start Frontend

```bash
cd frontend

# Start React dev server
npm start
```

Frontend will be available at: `http://localhost:3000`

---

## 📚 API Documentation

### Auto-Generated API Docs

Visit `http://localhost:8000/api/docs` for interactive Swagger UI documentation.

### Key API Endpoints

#### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - JWT login
- `POST /api/auth/verify-otp/` - OTP verification
- `POST /api/auth/refresh/` - Refresh JWT token
- `POST /api/auth/logout/` - Logout & blacklist token

#### Properties & Core
- `GET /api/core/properties/` - List properties (with filtering)
- `GET /api/core/properties/{id}/` - Property details
- `POST /api/core/properties/` - Create property (admin)

#### Valuation
- `POST /api/valuation/estimate/` - Get property valuation
- `POST /api/valuation/bulk-estimate/` - Batch valuation

#### Market Forecast
- `GET /api/forecast/trends/` - Market trends
- `GET /api/forecast/predictions/` - Price predictions

#### Legal AI
- `POST /api/legal/analyze-document/` - Analyze legal document
- `GET /api/legal/compliance-check/` - Compliance check

#### Investment
- `GET /api/investor/portfolio/` - User's portfolio
- `POST /api/investor/portfolio/add/` - Add property to portfolio
- `GET /api/investor/opportunities/` - Investment opportunities

#### Billing
- `POST /api/billing/create-checkout-session/` - Create payment session
- `POST /api/billing/confirm-payment/` - Confirm payment
- `GET /api/billing/subscription/` - Get subscription status

#### Chat
- `POST /api/chatbot/chat/` - Chat with AI assistant
- `GET /api/chatbot/history/` - Chat history

---

## 🚀 Deployment

### Deploy Backend to Render

1. **Create Render Account**
   - Go to [render.com](https://render.com)
   - Sign up with GitHub

2. **Create PostgreSQL Database**
   - Click "New +" → "PostgreSQL"
   - Name: `estatemind-db`
   - Region: Choose closest to you
   - Copy connection string

3. **Create Web Service**
   - Click "New +" → "Web Service"
   - Connect GitHub repository
   - Select `main` branch
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && gunicorn config.wsgi:application`
   - Set environment variables:
     ```
     DEBUG=False
     SECRET_KEY=your-production-secret
     DB_HOST=<render_postgres_host>
     DB_NAME=<render_postgres_db>
     DB_USER=<render_postgres_user>
     DB_PASSWORD=<render_postgres_password>
     ALLOWED_HOSTS=your-render-url.onrender.com
     STRIPE_SECRET_KEY=sk_live_...
     ```
   - Deploy

### Deploy Frontend to Vercel

1. **Create Vercel Account**
   - Go to [vercel.com](https://vercel.com)
   - Sign up with GitHub

2. **Import Project**
   - Click "Import Project"
   - Select your GitHub repository
   - Choose `frontend` directory as root
   - Set environment variables:
     ```
     REACT_APP_API_URL=https://your-backend.onrender.com/api
     REACT_APP_STRIPE_PUBLIC_KEY=pk_live_...
     ```
   - Deploy

3. **Update CORS**
   - Update backend `ALLOWED_HOSTS` to include Vercel domain
   - Update frontend `.env` with Render backend URL

---

## 🗄️ Database Setup

### PostgreSQL Local Setup

```bash
# Install PostgreSQL
# macOS: brew install postgresql
# Windows: Download from postgresql.org
# Linux: sudo apt install postgresql

# Create database and user
createdb estatemind_db
createuser estatemind_user
psql estatemind_db

# In psql:
ALTER USER estatemind_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE estatemind_db TO estatemind_user;
\q
```

### Run Migrations

```bash
cd backend
python manage.py migrate
python manage.py migrate --database=default
```

### Create Admin User

```bash
python manage.py createsuperuser
```

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
python manage.py test
python manage.py test valuation
python manage.py test legal
```

### Frontend Tests

```bash
cd frontend
npm test
npm run test:watch
```

---

## 📱 Key Features Explained

### Property Valuation
Uses trained CatBoost/XGBoost models with features:
- Location (latitude, longitude, delegation)
- Property characteristics (size, rooms, condition)
- Market comparables
- Historical trends

### Legal AI Assistant
- Document analysis using ChromaDB vector database
- Retrieval-Augmented Generation (RAG) pipeline
- Compliance checking against Tunisian regulations
- Real-time legal document recommendations

### Investment Portfolio
- Real-time portfolio tracking
- Risk assessment metrics
- Performance analytics
- Price alerts

### Climate Risk Assessment
- Climate data integration
- Risk scoring for properties
- Environmental impact analysis
- Future projections

---

## 🛠️ Development Commands

```bash
# Backend
cd backend

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver 0.0.0.0:8000

# Frontend
cd frontend

# Start dev server
npm start

# Build for production
npm run build

# Run tests
npm test
```

---

## 🔄 CI/CD Pipeline

The project includes automatic deployment on push to `main`:
1. GitHub Actions runs tests
2. Backend deploys to Render
3. Frontend deploys to Vercel
4. Database migrations run automatically

---

## 🐛 Troubleshooting

### Backend Issues

**Port Already in Use**
```bash
# On Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# On macOS/Linux
lsof -i :8000
kill -9 <PID>
```

**Database Connection Error**
- Verify PostgreSQL is running
- Check `DB_HOST`, `DB_PORT` in `.env`
- Ensure database and user exist

**ModuleNotFoundError**
```bash
pip install -r requirements.txt --upgrade
```

### Frontend Issues

**Port Already in Use**
```bash
npm start -- --port 3001
```

**Blank Page / 404 Errors**
- Verify `REACT_APP_API_URL` is correct
- Check browser console for errors
- Clear cache: `npm cache clean --force`

---

## 📞 Support & Documentation

- **API Docs**: `http://localhost:8000/api/docs`
- **Admin Panel**: `http://localhost:8000/admin`
- **GitHub**: [EstateMind Repository](https://github.com/fares279/EstateMind)

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👥 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 🙏 Acknowledgments

- Django & Django REST Framework community
- React community
- Stripe for payment processing
- OpenAI for AI capabilities
- Tunisian real estate market data sources

---

**Last Updated**: May 2026
**Version**: 1.0.0
**Status**: Production Ready ✅

For more information, visit [EstateMind GitHub](https://github.com/fares279/EstateMind)
