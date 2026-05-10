import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Topbar from './components/Navigation/Topbar';
import Footer from './components/Navigation/Footer';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';

// Auth Pages
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import VerifyOTPPage from './pages/auth/VerifyOTPPage';
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage';
import ResetPasswordPage from './pages/auth/ResetPasswordPage';

// Pages
import HomePage from './pages/HomePage';
import ExplorePage from './pages/ExplorePage';
import CommunityCampaignPage from './pages/CommunityCampaignPage';
import AnalyzePage from './pages/AnalyzePage';
import ValuatePage from './pages/ValuatePage';
import LegalAIPage from './pages/LegalAIPage';
import InvestLayout from './pages/invest/InvestLayout';
import InvestDashboard from './pages/invest/InvestDashboard';
import PortfolioPage from './pages/invest/PortfolioPage';
import ScannerPage from './pages/invest/ScannerPage';
import OpportunitiesPage from './pages/invest/OpportunitiesPage';
import RiskPage from './pages/invest/RiskPage';
import SimulatePage from './pages/SimulatePage';
import AccountDashboardPage from './pages/AccountDashboardPage';
import AccountSettingsPage from './pages/AccountSettingsPage';
import AccountApiKeysPage from './pages/AccountApiKeysPage';
import AccountAlertsPage from './pages/AccountAlertsPage';
import NotFoundPage from './pages/NotFoundPage';
import AIChatWidget from './components/AIChatWidget';

function AppLayout() {
  const location = useLocation();
  const authPaths = ['/login', '/register', '/verify-otp', '/forgot-password', '/reset-password'];
  const isAuthPage = authPaths.includes(location.pathname);

  return (
    <>
      {!isAuthPage && <Topbar />}
      <Routes>
        {/* Home */}
        <Route path="/" element={<HomePage />} />

        {/* Auth Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-otp" element={<VerifyOTPPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

          {/* Explore Route - Unified Workspace */}
          <Route path="/explore" element={<ExplorePage />} />

          {/* Analyze Route */}
          <Route path="/analyze" element={<AnalyzePage />} />

          {/* Valuate Route */}
          <Route
            path="/valuate"
            element={
              <ProtectedRoute>
                <ValuatePage />
              </ProtectedRoute>
            }
          />

          {/* Invest Routes — require authentication */}
          <Route
            path="/invest"
            element={
              <ProtectedRoute>
                <InvestLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<InvestDashboard />} />
            <Route path="portfolio"     element={<PortfolioPage />} />
            <Route path="scanner"       element={<ScannerPage />} />
            <Route path="opportunities" element={<OpportunitiesPage />} />
            <Route path="risk"          element={<RiskPage />} />
          </Route>

          {/* Simulate */}
          <Route path="/simulate" element={<SimulatePage />} />

          {/* Legal Route */}
          <Route path="/legal" element={<LegalAIPage />} />

          {/* Community Route */}
          <Route path="/community" element={<CommunityCampaignPage />} />

          {/* Account Routes */}
          <Route
            path="/account/dashboard"
            element={
              <ProtectedRoute>
                <AccountDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/settings"
            element={
              <ProtectedRoute>
                <AccountSettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/api-keys"
            element={
              <ProtectedRoute>
                <AccountApiKeysPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/account/alerts"
            element={
              <ProtectedRoute>
                <AccountAlertsPage />
              </ProtectedRoute>
            }
          />

          {/* Catch-all 404 Route */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        {!isAuthPage && <Footer />}
        {!isAuthPage && <AIChatWidget />}
      </>
    );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppLayout />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
