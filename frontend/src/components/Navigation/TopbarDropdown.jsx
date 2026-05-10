import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';

const TopbarDropdown = ({ menu, onClose }) => {
  const columnCount = Math.ceil(menu.sections.length / 2);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-max min-w-[900px] bg-navy-950 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-xl p-6 grid grid-cols-4 gap-8"
      onMouseLeave={onClose}
    >
      {menu.sections.map((section, idx) => (
        <div key={idx}>
          <h3 className="text-xs uppercase tracking-wide text-gray-500 font-semibold mb-3">
            {section.title}
          </h3>
          <div className="space-y-1">
            {section.items.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className="block px-3 py-2 rounded-lg text-sm text-gray-300 hover:text-white hover:bg-white/5 transition-all duration-150 flex items-center gap-2 group"
              >
                <span className="text-lg group-hover:scale-110 transition-transform">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </motion.div>
  );
};

export default TopbarDropdown;
