import React, { useEffect, useMemo, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import PropertyCard from './PropertyCard';

export default function PropertyList({
  properties = [],
  selectedProperty,
  onPropertySelect,
  onViewDetails,
  filters,
  onFilterChange,
  loading,
  error,
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 9;
  const listRef = useRef(null);
  const displayProperties = properties;

  // Pagination logic
  const totalPages = Math.ceil(displayProperties.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedProperties = displayProperties.slice(startIndex, endIndex);

  useEffect(() => {
    if (!selectedProperty || displayProperties.length === 0) return;

    const selectedIndex = displayProperties.findIndex((p) => p.id === selectedProperty.id);
    if (selectedIndex === -1) return;

    const targetPage = Math.floor(selectedIndex / itemsPerPage) + 1;
    if (targetPage !== currentPage) {
      setCurrentPage(targetPage);
      setTimeout(() => {
        listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 0);
    }
  }, [selectedProperty, displayProperties, currentPage]);

  const paginationWindow = useMemo(() => {
    const maxVisible = 5;
    if (totalPages <= maxVisible) {
      return Array.from({ length: totalPages }, (_, idx) => idx + 1);
    }

    let start = Math.max(1, currentPage - 2);
    let end = start + maxVisible - 1;

    if (end > totalPages) {
      end = totalPages;
      start = end - maxVisible + 1;
    }

    return Array.from({ length: end - start + 1 }, (_, idx) => start + idx);
  }, [currentPage, totalPages]);

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
      setTimeout(() => {
        listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 0);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
      setTimeout(() => {
        listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 0);
    }
  };

  const handlePageClick = (page) => {
    setCurrentPage(page);
    setTimeout(() => {
      listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5 },
    },
  };

  return (
    <motion.div
      ref={listRef}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="w-full"
    >
      {/* Header */}
      <div className="mb-8">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center justify-between"
        >
          <div>
            <h3 className="text-2xl font-black text-white mb-1">
              Available <span className="text-[#FF6B35]">Properties</span>
            </h3>
            <p className="text-gray-400 text-sm">
              {loading ? 'Loading properties…' : `${displayProperties.length} properties found`} • Click to view on map
            </p>
          </div>
          <div className="text-right">
            <span className="inline-block bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] px-4 py-2 rounded-lg text-sm font-mono">
              Page {Math.min(currentPage, Math.max(totalPages, 1))} of {Math.max(totalPages, 1)}
            </span>
          </div>
        </motion.div>
      </div>

      {/* Filters */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-3">
        <select
          value={filters.property_type}
          onChange={(e) => onFilterChange({ property_type: e.target.value })}
          className="px-3 py-2 rounded-lg bg-slate-900/70 border border-slate-700 text-gray-200 text-sm"
        >
          <option value="">All Types</option>
          <option value="apartment">Apartment</option>
          <option value="house">House</option>
          <option value="land">Land</option>
          <option value="commercial">Commercial</option>
        </select>

        <input
          type="number"
          value={filters.price_min}
          onChange={(e) => onFilterChange({ price_min: e.target.value })}
          placeholder="Min Price"
          className="px-3 py-2 rounded-lg bg-slate-900/70 border border-slate-700 text-gray-200 text-sm"
        />

        <input
          type="number"
          value={filters.price_max}
          onChange={(e) => onFilterChange({ price_max: e.target.value })}
          placeholder="Max Price"
          className="px-3 py-2 rounded-lg bg-slate-900/70 border border-slate-700 text-gray-200 text-sm"
        />

        <button
          onClick={() =>
            onFilterChange({
              property_type: '',
              price_min: '',
              price_max: '',
              governorate: '',
              delegation: '',
            })
          }
          className="px-3 py-2 rounded-lg bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] text-sm font-semibold hover:bg-[#FF6B35] hover:text-black transition"
        >
          Reset Filters
        </button>
      </div>

      {error && (
        <div className="mb-6 p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Properties Grid */}
      <motion.div
        variants={containerVariants}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {paginatedProperties.map((property) => (
          <motion.div
            key={property.id}
            variants={itemVariants}
            onClick={() => onPropertySelect(property)}
            className={`cursor-pointer transition-all duration-300 transform ${
              selectedProperty?.id === property.id
                ? 'ring-2 ring-[#FF6B35] scale-105'
                : 'hover:scale-102'
            }`}
          >
            <PropertyCard property={property} isSelected={selectedProperty?.id === property.id} onViewDetails={onViewDetails} />
          </motion.div>
        ))}
      </motion.div>

      {/* Empty State */}
      {displayProperties.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <p className="text-gray-500 text-lg">No properties found</p>
          <p className="text-gray-600 text-sm mt-2">Try adjusting your filters</p>
        </motion.div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="flex items-center justify-center gap-4 mt-12"
        >
          <button
            onClick={() => handlePageClick(1)}
            disabled={currentPage === 1}
            className={`w-10 h-10 rounded-lg font-semibold transition-all duration-300 ${
              currentPage === 1
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] hover:bg-[#FF6B35] hover:text-black'
            }`}
            aria-label="First page"
          >
            «
          </button>

          {/* Previous Button */}
          <button
            onClick={handlePrevPage}
            disabled={currentPage === 1}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-300 ${
              currentPage === 1
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] hover:bg-[#FF6B35] hover:text-black'
            }`}
          >
            <ChevronLeft size={18} />
            <span className="hidden sm:inline">Previous</span>
          </button>

          {/* Page Numbers */}
          <div className="flex items-center gap-2">
            {paginationWindow.map((page) => (
              <button
                key={page}
                onClick={() => handlePageClick(page)}
                className={`w-10 h-10 rounded-lg font-medium transition-all duration-300 ${
                  currentPage === page
                    ? 'bg-[#FF6B35] text-black font-bold'
                    : 'bg-gray-800/50 text-gray-400 hover:bg-gray-750 hover:text-white border border-gray-700'
                }`}
              >
                {page}
              </button>
            ))}
          </div>

          {/* Next Button */}
          <button
            onClick={handleNextPage}
            disabled={currentPage === totalPages}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-300 ${
              currentPage === totalPages
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] hover:bg-[#FF6B35] hover:text-black'
            }`}
          >
            <span className="hidden sm:inline">Next</span>
            <ChevronRight size={18} />
          </button>

          <button
            onClick={() => handlePageClick(totalPages)}
            disabled={currentPage === totalPages}
            className={`w-10 h-10 rounded-lg font-semibold transition-all duration-300 ${
              currentPage === totalPages
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-[#FF6B35]/10 border border-[#FF6B35]/30 text-[#FF6B35] hover:bg-[#FF6B35] hover:text-black'
            }`}
            aria-label="Last page"
          >
            »
          </button>
        </motion.div>
      )}
    </motion.div>
  );
}
