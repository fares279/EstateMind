/**
 * Legal AI - Q&A with Source Citations
 * Shows legal answers grounded in sources
 */

import React, { useState } from 'react';
import { askLegalQuestion } from '../../../services/api-modules';
import { SourceCitation, SkeletonLoader, ErrorFallback } from '../../../components/common/CommonComponents';

export const LegalAnswerCard = ({ answer, sources, grounding, confidenceLevel }) => {
  const getGroundingColor = () => {
    switch (confidenceLevel) {
      case 'HIGH': return 'text-green-400';
      case 'MEDIUM': return 'text-yellow-400';
      case 'LOW': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex justify-between items-start mb-2">
        <div className="text-sm text-gray-400">Legal Answer</div>
        <div className={`text-xs font-semibold ${getGroundingColor()}`}>
          {confidenceLevel} Grounding ({grounding}%)
        </div>
      </div>

      <div className="text-gray-200 leading-relaxed mb-4">{answer}</div>

      {confidenceLevel === 'LOW' && (
        <div className="bg-red-900/20 border border-red-700 rounded p-2 mb-3 text-xs text-red-300">
          ⚠ Low grounding: Less than 60% of answer backed by sources
        </div>
      )}

      <div className="text-xs text-gray-500 mb-2 font-semibold">Sources:</div>
      <div className="space-y-2">
        {sources &&
          sources.map((source, i) => (
            <SourceCitation
              key={i}
              source={`${source.law_name}, Article ${source.article}`}
              similarity={source.similarity_score}
              confidence={source.confidence_label}
            />
          ))}
      </div>
    </div>
  );
};

export const LegalQAInterface = () => {
  const [input, setInput] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAsk = async () => {
    if (!input.trim()) return;

    try {
      setLoading(true);
      const response = await askLegalQuestion(input);
      setAnswer(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to get answer'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <div className="mb-4">
        <label className="block text-sm font-semibold text-white mb-2">Ask a Legal Question</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder="e.g., What are the rental restrictions for foreign investors?"
            className="flex-1 bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500"
            disabled={loading}
          />
          <button
            onClick={handleAsk}
            disabled={loading || !input.trim()}
            className="px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded font-semibold disabled:opacity-50 transition"
          >
            {loading ? '...' : 'Ask'}
          </button>
        </div>
      </div>

      {error && <ErrorFallback error={error} retry={() => handleAsk()} />}
      {loading && <SkeletonLoader variant="card" lines={3} />}
      {answer && (
        <LegalAnswerCard
          answer={answer.answer_text}
          sources={answer.sources}
          grounding={answer.grounding_pct}
          confidenceLevel={answer.grounding_label}
        />
      )}
    </div>
  );
};

export default LegalQAInterface;
