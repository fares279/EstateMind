/**
 * AI Chatbot
 * ChatMessage - Individual message display with feedback
 * ChatInterface - Full conversation widget
 */

import React, { useState, useRef, useEffect } from 'react';
import { sendChatMessage, submitChatFeedback } from '../../../services/api-modules';
import { FallbackNotice, SkeletonLoader } from '../../../components/shared/CommonComponents';

export const ChatMessage = ({ message, onFeedback }) => {
  const { id, text, sources, quality_score, is_fallback, fallback_reason, timestamp } = message;
  const [feedbackGiven, setFeedbackGiven] = useState(null);

  const handleFeedback = (feedback) => {
    setFeedbackGiven(feedback);
    onFeedback(id, feedback);
  };

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center text-white text-sm flex-shrink-0 font-semibold">
        AI
      </div>

      <div className="flex-1">
        <div className="bg-gray-750 rounded-2xl rounded-tl-sm p-4">
          {is_fallback && fallback_reason && <FallbackNotice reason={fallback_reason} />}

          <div className="text-gray-200 leading-relaxed text-sm">{text}</div>

          {sources && sources.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-3">
              {sources.map((src, i) => (
                <span key={i} className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">
                  {src}
                </span>
              ))}
            </div>
          )}

          {quality_score !== undefined && (
            <div className="mt-2 flex items-center gap-2">
              <div className="flex-1 h-0.5 bg-gray-700 rounded">
                <div className="h-0.5 bg-orange-500 rounded" style={{ width: `${quality_score * 100}%` }} />
              </div>
              <span className="text-xs text-gray-600">{quality_score.toFixed(2)}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2 mt-1 ml-2">
          <button
            onClick={() => handleFeedback('helpful')}
            className={`text-xs transition-colors flex items-center gap-1 ${
              feedbackGiven === 'helpful' ? 'text-green-400' : 'text-gray-600 hover:text-green-400'
            }`}
            disabled={feedbackGiven !== null}
          >
            <span>👍</span> Helpful
          </button>
          <button
            onClick={() => handleFeedback('not_helpful')}
            className={`text-xs transition-colors flex items-center gap-1 ${
              feedbackGiven === 'not_helpful' ? 'text-red-400' : 'text-gray-600 hover:text-red-400'
            }`}
            disabled={feedbackGiven !== null}
          >
            <span>👎</span> Not helpful
          </button>
        </div>
      </div>
    </div>
  );
};

export const ChatInterface = () => {
  const [conversationId] = useState(() => `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = {
      id: `msg_${Date.now()}`,
      text: input,
      role: 'user',
      intent: '',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(input, conversationId);
      setMessages((prev) => [...prev, { ...response, role: 'assistant' }]);
    } catch (error) {
      const errorMessage = {
        id: `msg_${Date.now()}`,
        text: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        role: 'assistant',
        intent: 'error',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (messageId, feedback) => {
    try {
      await submitChatFeedback(messageId, feedback);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-800 rounded-xl border border-gray-700">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 py-12">
            <div className="text-3xl mb-2">💬</div>
            <div className="text-sm">Ask me about properties, valuations, legal questions, or investment grades!</div>
          </div>
        )}

        {messages.map((msg) =>
          msg.role === 'user' ? (
            <div key={msg.id} className="flex gap-3 justify-end mb-4">
              <div className="bg-orange-600 rounded-2xl rounded-tr-sm p-4 max-w-xs">
                <div className="text-white text-sm">{msg.text}</div>
              </div>
            </div>
          ) : (
            <ChatMessage key={msg.id} message={msg} onFeedback={handleFeedback} />
          )
        )}

        {loading && (
          <div className="flex gap-3 mb-4">
            <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center text-white text-sm flex-shrink-0 font-semibold">
              AI
            </div>
            <div className="bg-gray-750 rounded-2xl rounded-tl-sm p-4">
              <SkeletonLoader lines={2} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder="Ask me anything..."
            disabled={loading}
            className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 disabled:opacity-50"
          />
          <button
            onClick={handleSendMessage}
            disabled={loading || !input.trim()}
            className="px-6 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 transition font-semibold"
          >
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
