import React from 'react';
import { LogOut, Settings, Key, Bell, Zap } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';

const UserProfileDropdown = ({ isOpen, onClose }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    logout();
    onClose();
    navigate('/');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="absolute top-full right-0 mt-2 w-64 bg-navy-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50"
          onMouseLeave={onClose}
        >
          {/* Header */}
          <div className="p-4 border-b border-white/10 bg-navy-950">
            <p className="font-semibold text-white">{user?.full_name || 'User'}</p>
            <p className="text-xs text-gray-500">{user?.email || 'Not logged in'}</p>
          </div>

          {/* Account Section */}
          <div className="p-3 space-y-1 border-b border-white/10">
            <Link
              to="/account/dashboard"
              className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
              onClick={onClose}
            >
              <Zap size={16} />
              Dashboard
            </Link>
            <Link
              to="/account/settings"
              className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
              onClick={onClose}
            >
              <Settings size={16} />
              Settings
            </Link>
            <Link
              to="/account/api-keys"
              className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
              onClick={onClose}
            >
              <Key size={16} />
              API Keys
            </Link>
          </div>

          {/* Notifications Section */}
          <div className="p-3 space-y-1 border-b border-white/10">
            <Link
              to="/account/alerts"
              className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
              onClick={onClose}
            >
              <Bell size={16} />
              Alerts
            </Link>
          </div>

          {/* System Section */}
          <div className="p-3">
            <button 
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default UserProfileDropdown;
