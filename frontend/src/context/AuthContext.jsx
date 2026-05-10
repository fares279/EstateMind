import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { canAccessPlan, normalizePlan } from '../utils/accessControl';
import { trackUserActivity, createCheckoutSession, devUpgradePlan } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [, setRefreshToken] = useState(localStorage.getItem('refresh_token'));

  const API_BASE =
    (typeof window !== 'undefined' && window.__API_BASE__) ||
    process.env.REACT_APP_API_URL ||
    'http://localhost:8000/api';

  const clearStoredAuth = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setRefreshToken(null);
    setUser(null);
  }, []);

  const refreshStoredToken = useCallback(async () => {
    const storedRefreshToken = localStorage.getItem('refresh_token');
    if (!storedRefreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await axios.post(`${API_BASE}/auth/token/refresh/`, {
      refresh: storedRefreshToken,
    });
    const access = response.data?.access;
    const refresh = response.data?.refresh;

    if (!access) {
      throw new Error('Token refresh response did not include an access token');
    }

    localStorage.setItem('access_token', access);
    if (refresh) {
      localStorage.setItem('refresh_token', refresh);
      setRefreshToken(refresh);
    }
    setToken(access);
    return access;
  }, [API_BASE]);

  // Verify token and fetch current user
  const verifyToken = useCallback(async (token) => {
    try {
      if (!token) {
        throw new Error('No access token available');
      }
      const response = await axios.get(`${API_BASE}/auth/me/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(response.data);
      setToken(token);
    } catch (err) {
      try {
        const access = await refreshStoredToken();
        const response = await axios.get(`${API_BASE}/auth/me/`, {
          headers: { Authorization: `Bearer ${access}` },
        });
        setUser(response.data);
      } catch (refreshErr) {
        clearStoredAuth();
      }
    } finally {
      setLoading(false);
    }
  }, [API_BASE, clearStoredAuth, refreshStoredToken]);

  // Initialize auth on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      verifyToken(token);
    } else if (localStorage.getItem('refresh_token')) {
      verifyToken(null);
    } else {
      setLoading(false);
    }
  }, [verifyToken]);

  // Register
  const register = async (email, full_name, password, password_confirm, phone = '') => {
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/auth/register/`, {
        email,
        full_name,
        password,
        password_confirm,
        phone,
      });
      return {
        success: true,
        data: response.data,
        message: 'Registration successful. Please verify your email with the OTP.',
      };
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.response?.data?.email?.[0] || 'Registration failed';
      setError(errorMsg);
      throw err;
    }
  };

  // Verify OTP
  const verifyOTP = async (email, otp) => {
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/auth/verify_otp/`, {
        email,
        otp,
      });
      setUser(response.data.user);
      return { success: true, message: 'Email verified successfully!' };
    } catch (err) {
      const errorMsg = err.response?.data?.otp?.[0] || 'OTP verification failed';
      setError(errorMsg);
      throw err;
    }
  };

  // Resend OTP
  const resendOTP = async (email) => {
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/auth/resend_otp/`, { email });
      return { success: true, message: response.data.message };
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Failed to resend OTP';
      setError(errorMsg);
      throw err;
    }
  };

  // Login
  const login = async (email, password) => {
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/auth/token/`, {
        email,
        password,
      });

      const { access, refresh, user } = response.data;
      
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
      
      setToken(access);
      setRefreshToken(refresh);
      setUser(user);

      return {
        success: true,
        user,
        message: 'Login successful!',
      };
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Login failed. Check your credentials.';
      setError(errorMsg);
      throw err;
    }
  };

  // Logout
  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    setError(null);
  };

  // Forgot password
  const forgotPassword = async (email) => {
    setError(null);
    try {
      await axios.post(`${API_BASE}/auth/forgot_password/`, { email });
      return {
        success: true,
        message: 'If this email exists, you will receive a password reset link.',
      };
    } catch (err) {
      throw err;
    }
  };

  // Reset password
  const resetPassword = async (token, password, password_confirm) => {
    setError(null);
    try {
      await axios.post(`${API_BASE}/auth/reset_password/`, {
        token,
        password,
        password_confirm,
      });
      return {
        success: true,
        message: 'Password reset successfully! You can now login.',
      };
    } catch (err) {
      const errorMsg = err.response?.data?.password?.[0] || err.response?.data?.token?.[0] || 'Password reset failed';
      setError(errorMsg);
      throw err;
    }
  };

  // Change password
  const changePassword = async (old_password, password, password_confirm) => {
    setError(null);
    try {
      await axios.post(
        `${API_BASE}/auth/change_password/`,
        { old_password, password, password_confirm },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      return { success: true, message: 'Password changed successfully' };
    } catch (err) {
      const errorMsg = err.response?.data?.password?.[0] || 'Password change failed';
      setError(errorMsg);
      throw err;
    }
  };

  // Update profile
  const updateProfile = async (data) => {
    setError(null);
    try {
      const response = await axios.patch(
        `${API_BASE}/auth/update_profile/`,
        data,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setUser(response.data.user);
      return { success: true, message: 'Profile updated successfully', user: response.data.user };
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Profile update failed';
      setError(errorMsg);
      throw err;
    }
  };

  const deleteAccount = async (password) => {
    setError(null);
    try {
      const response = await axios.post(
        `${API_BASE}/auth/delete-account/`,
        { password },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      logout();
      return { success: true, message: response.data?.message || 'Account deleted' };
    } catch (err) {
      const errorMsg =
        err.response?.data?.password ||
        err.response?.data?.detail ||
        'Account deletion failed';
      setError(errorMsg);
      throw err;
    }
  };

  const value = {
    user,
    loading,
    error,
    token,
    plan: normalizePlan(user?.plan),
    hasAccess: (requiredPlan) => canAccessPlan(user?.plan, requiredPlan),
    isAuthenticated: !!user && !!token,
    register,
    verifyOTP,
    resendOTP,
    login,
    logout,
    forgotPassword,
    resetPassword,
    changePassword,
    updateProfile,
    deleteAccount,
    trackActivity: async (activity_type, feature, metadata = {}) => {
      if (!token) return;
      try {
        await trackUserActivity({ activity_type, feature, metadata });
      } catch (err) {
        // Swallow activity tracking errors to avoid interrupting UX.
      }
    },
    upgradePlan: async (targetPlan) => {
      try {
        const response = await createCheckoutSession(targetPlan);
        const checkoutUrl = response?.data?.checkout_url;
        if (checkoutUrl) {
          window.location.href = checkoutUrl;
          return response.data;
        }

        throw new Error('Checkout URL missing from payment response');
      } catch (err) {
        const isLocalDev = ['localhost', '127.0.0.1'].includes(window.location.hostname);

        if (isLocalDev) {
          try {
            const fallbackResponse = await devUpgradePlan(targetPlan);
            const upgradedUser = {
              ...(user || {}),
              plan: fallbackResponse.data?.plan || targetPlan,
              is_plan_active: true,
            };
            setUser(upgradedUser);
            return fallbackResponse.data;
          } catch (fallbackErr) {
            const message = fallbackErr.response?.data?.error || fallbackErr.message || 'Upgrade failed';
            setError(message);
            throw fallbackErr;
          }
        }

        const message = err.response?.data?.error || err.message || 'Upgrade failed';
        setError(message);
        throw err;
      }
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
