import React, { useState } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Menu, X, Search, Bell, User, ChevronDown } from 'lucide-react';
import TopbarDropdown from './TopbarDropdown';
import UserProfileDropdown from './UserProfileDropdown';
import { useAuth } from '../../context/AuthContext';

const menuStructure = [
  { label: 'Home', path: '/', emoji: '🏠' },
  { label: 'Explore', path: '/explore', emoji: '🗺️' },
  {
    label: 'Analyze',
    emoji: '📊',
    path: '/analyze'
  },
  { label: 'Valuate', path: '/valuate', emoji: '💲' },
  {
    label: 'Invest',
    emoji: '💰',
    path: '/invest'
  },
  {
    label: 'Simulate',
    emoji: '🔮',
    path: '/simulate'
  },
  { label: 'Legal AI', path: '/legal', emoji: '🤖' },
  {
    label: 'Community',
    emoji: '👥',
    path: '/community'
  }
];

export default function Topbar() {
  const location = useLocation();
  const { user, loading } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState(null);
  const [activeSubmenu, setActiveSubmenu] = useState(null);
  const [showProfileDropdown, setShowProfileDropdown] = useState(false);

  const isMenuActive = (menuLabel) => {
    if (location.pathname === '/' && menuLabel === 'Home') return true;
    return location.pathname.startsWith(`/${menuLabel.toLowerCase().replace(/\s+/g, '')}`);
  };

  const isSubmenuActive = (path) => location.pathname === path;

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-b from-[#1A2332]/95 to-[#0B0F19]/80 backdrop-blur-lg border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-20">
          {/* Logo with Text */}
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition">
            <img src="/images/logo_without_name.png" alt="EstateMind" className="h-10" />
            <span className="text-xl font-bold text-[#FF6B35] hidden sm:inline">EstateMind</span>
          </Link>

          {/* Desktop Menu */}
          <div className="hidden lg:flex items-center gap-1">
            {menuStructure.map((menu) => (
              <div key={menu.label} className="relative group">
                {menu.path ? (
                  <Link
                    to={menu.path}
                    className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                      isMenuActive(menu.label)
                        ? 'text-[#FF6B35] bg-white/5'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {menu.label}
                  </Link>
                ) : (
                  <button
                    onMouseEnter={() => setActiveMenu(menu.label)}
                    className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                      isMenuActive(menu.label)
                        ? 'text-[#FF6B35] bg-white/5'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {menu.label}
                    <ChevronDown size={16} />
                  </button>
                )}

                {/* Mega Dropdown */}
                {menu.items && activeMenu === menu.label && (
                  <div
                    className="absolute top-full left-0 mt-0 bg-[#1A2332] backdrop-blur-lg border border-white/10 rounded-xl shadow-2xl p-3 flex flex-col gap-2 min-w-max"
                    onMouseEnter={() => setActiveMenu(menu.label)}
                    onMouseLeave={() => setActiveMenu(null)}
                  >
                    {menu.items.map((item) => (
                      <Link
                        key={item.label}
                        to={item.path}
                        className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                          isSubmenuActive(item.path)
                            ? 'bg-[#FF6B35] border border-[#FF6B35] text-white'
                            : 'bg-gray-800 border border-gray-700 text-gray-300 hover:border-[#FF6B35] hover:text-[#FF6B35] hover:bg-gray-700'
                        }`}
                        onClick={() => setActiveMenu(null)}
                      >
                        <span>{item.emoji}</span>
                        <span className="font-semibold">{item.label}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Right Side Icons */}
          <div className="flex items-center gap-4">
            {/* Notifications - Only show when logged in */}
            {user && (
              <button className="relative p-2 text-gray-300 hover:text-[#FF6B35] transition">
                <Bell size={20} />
                <span className="absolute top-1 right-1 w-2 h-2 bg-[#FF6B35] rounded-full"></span>
              </button>
            )}

            {/* Auth Buttons or Profile Dropdown */}
            {!loading && (
              <>
                {user ? (
                  // Logged In: Show Profile Dropdown
                  <div className="relative">
                    <button
                      onClick={() => setShowProfileDropdown(!showProfileDropdown)}
                      className="p-2 text-gray-300 hover:text-[#FF6B35] transition"
                    >
                      <User size={20} />
                    </button>
                    <UserProfileDropdown 
                      isOpen={showProfileDropdown} 
                      onClose={() => setShowProfileDropdown(false)}
                    />
                  </div>
                ) : (
                  // Not Logged In: Show Auth Buttons
                  <div className="hidden sm:flex items-center gap-3">
                    <Link
                      to="/login"
                      className="px-4 py-2 text-gray-300 hover:text-white transition"
                    >
                      Sign In
                    </Link>
                    <Link
                      to="/register"
                      className="px-4 py-2 bg-[#FF6B35] hover:bg-[#E55A1F] text-white rounded-lg font-semibold transition-all"
                    >
                      Sign Up
                    </Link>
                  </div>
                )}
              </>
            )}

            {/* Mobile Menu Toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 text-gray-300 hover:text-[#FF6B35] transition"
            >
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden pb-4 border-t border-white/10">
            {menuStructure.map((menu) => (
              <div key={menu.label}>
                {menu.path ? (
                  <Link
                    to={menu.path}
                    className={`block px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                      isMenuActive(menu.label)
                        ? 'text-[#FF6B35] bg-white/5'
                        : 'text-gray-300 hover:text-white hover:bg-white/5'
                    }`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {menu.label}
                  </Link>
                ) : (
                  <>
                    <button
                      onClick={() =>
                        setActiveMenu(activeMenu === menu.label ? null : menu.label)
                      }
                      className="w-full text-left px-4 py-2 text-gray-300 hover:text-white flex items-center justify-between gap-2"
                    >
                      <div className="flex items-center gap-2">
                        {menu.label}
                      </div>
                      <ChevronDown
                        size={16}
                        className={`transition-transform ${
                          activeMenu === menu.label ? 'rotate-180' : ''
                        }`}
                      />
                    </button>
                    {activeMenu === menu.label && (
                      <div className="pl-4 space-y-1">
                        {menu.items.map((item) => (
                          <Link
                            key={item.label}
                            to={item.path}
                            className={`block px-4 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                              isSubmenuActive(item.path)
                                ? 'bg-[#FF6B35] text-white'
                                : 'text-gray-400 hover:text-white'
                            }`}
                            onClick={() => {
                              setMobileMenuOpen(false);
                              setActiveMenu(null);
                            }}
                          >
                            <span>{item.emoji}</span>
                            {item.label}
                          </Link>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}

            {/* Mobile Auth Buttons */}
            {!loading && !user && (
              <div className="mt-4 px-4 space-y-2 border-t border-white/10 pt-4">
                <Link
                  to="/login"
                  className="block w-full px-4 py-2 text-center text-gray-300 hover:text-white transition"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="block w-full px-4 py-2 text-center bg-[#FF6B35] hover:bg-[#E55A1F] text-white rounded-lg font-semibold transition-all"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Sign Up
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
