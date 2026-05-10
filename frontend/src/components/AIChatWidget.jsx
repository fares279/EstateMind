/**
 * EstateMind AI Chat Widget
 * Floating bottom-right button → full-screen chat popup
 * Professional design, multi-turn, markdown rendering, suggestion chips
 */
import React, {
  useState, useEffect, useRef, useCallback, useMemo,
} from 'react';
import {
  X, Send, Sparkles, Minimize2, RotateCcw, Globe2,
  ChevronDown, Building2, TrendingUp, MapPin, Zap,
  MessageCircle,
} from 'lucide-react';
import { chatSendMessage } from '../services/api';

/* ── Constants ──────────────────────────────────────────────────────────────── */
const ORANGE      = '#FF6B35';
const SESSION_KEY = 'estatemind_chat_session';

const WELCOME = {
  id: 'welcome',
  role: 'assistant',
  text: `## Welcome to EstateMind AI 🏠

I'm your **personal real estate advisor** for the Tunisian market — powered by live data from all 278 delegations.

**I can help you with:**
- 📊 Current prices across every governorate
- 📈 12-month price forecasts & trend analysis
- 💰 Investment yields and opportunity ranking
- 🏦 Mortgage guidance and affordability checks
- 🌍 Climate risk and neighbourhood comparisons

What's on your mind?`,
  suggestions: [
    'Apartment prices in Tunis?',
    'Best investment regions 2026?',
    'Compare Sousse vs Sfax',
    'Mortgage guide Tunisia',
  ],
  ts: Date.now(),
};

const LANGS = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'fr', label: 'FR', name: 'Français' },
  { code: 'ar', label: 'AR', name: 'العربية' },
];

/* ── Markdown-lite renderer ──────────────────────────────────────────────────── */
function MarkdownText({ text }) {
  const html = useMemo(() => {
    let t = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Code inline
    t = t.replace(/`([^`]+)`/g, '<code class="bg-white/10 rounded px-1 text-[#FFB38F] text-xs font-mono">$1</code>');
    // Bold
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white font-bold">$1</strong>');
    // Italic
    t = t.replace(/\*([^*]+)\*/g, '<em class="text-gray-300">$1</em>');
    // H2
    t = t.replace(/^## (.+)$/gm, '<p class="text-base font-black text-white mt-1 mb-2">$1</p>');
    // H3
    t = t.replace(/^### (.+)$/gm, '<p class="text-sm font-bold text-[#FF6B35] mt-2 mb-1">$1</p>');
    // Bullet list items
    t = t.replace(/^- (.+)$/gm, '<div class="flex gap-1.5 mt-1"><span class="text-[#FF6B35] mt-0.5 flex-shrink-0 text-xs">•</span><span class="flex-1">$1</span></div>');
    // Numbered
    t = t.replace(/^(\d+)\. (.+)$/gm, '<div class="flex gap-1.5 mt-1"><span class="text-[#FF6B35] text-xs font-bold min-w-[16px]">$1.</span><span class="flex-1">$2</span></div>');
    // Blank lines → spacing (must use proper closing tag, not self-closing)
    t = t.replace(/\n\n/g, '<div class="h-2"></div>');
    // Single newlines → line break (only converts remaining \n not already part of block elements)
    t = t.replace(/\n/g, '<br>');

    return t;
  }, [text]);

  return (
    <div
      className="text-sm text-gray-200 leading-relaxed"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/* ── Typing dots ─────────────────────────────────────────────────────────────── */
function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map(i => (
        <span key={i} className="w-1.5 h-1.5 rounded-full bg-[#FF6B35]"
          style={{ animation: `chatBounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />
      ))}
    </div>
  );
}

/* ── Single message bubble ──────────────────────────────────────────────────── */
function MessageBubble({ msg, onSuggestion }) {
  const isUser = msg.role === 'user';
  const isTyping = msg.role === 'typing';

  if (isTyping) {
    return (
      <div className="flex items-end gap-2.5">
        <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-[#FF6B35] to-[#ff9a35] flex items-center justify-center flex-shrink-0">
          <Sparkles size={13} className="text-white" />
        </div>
        <div className="bg-white/[0.07] border border-white/[0.08] rounded-2xl rounded-bl-md px-4 py-3">
          <TypingDots />
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-end gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-[#FF6B35] to-[#ff9a35] flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-500/20">
          <Sparkles size={13} className="text-white" />
        </div>
      )}

      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div className={`rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? 'bg-gradient-to-br from-[#FF6B35] to-[#e55a2b] text-white rounded-br-md'
            : 'bg-white/[0.07] border border-white/[0.08] rounded-bl-md'
        }`}>
          {isUser
            ? <p className="text-sm text-white leading-relaxed">{msg.text}</p>
            : <MarkdownText text={msg.text} />
          }
        </div>

        {/* Suggestion chips */}
        {!isUser && msg.suggestions?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-0.5">
            {msg.suggestions.map((s, i) => (
              <button key={i} onClick={() => onSuggestion(s)}
                className="text-[11px] text-[#FFB38F] border border-[#FF6B35]/30 bg-[#FF6B35]/8 rounded-full px-2.5 py-1 hover:bg-[#FF6B35]/20 hover:border-[#FF6B35]/60 transition-all leading-tight text-left">
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-gray-600 px-1">
          {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}

/* ── Quick action pills ─────────────────────────────────────────────────────── */
const QUICK_ACTIONS = [
  { label: 'Prices', icon: Building2, q: 'What are current property prices?' },
  { label: 'Invest', icon: TrendingUp, q: 'Best investment opportunities in Tunisia 2026?' },
  { label: 'Map',    icon: MapPin,    q: 'Which governorate has the best value for money?' },
  { label: 'Trend',  icon: Zap,       q: 'What are the price growth trends for 2026?' },
];

/* ══════════════════════════════════════════════════════════════════════════════
   Main Widget
══════════════════════════════════════════════════════════════════════════════ */
export default function AIChatWidget() {
  const [open,         setOpen]         = useState(false);
  const [minimised,    setMinimised]    = useState(false);
  const [messages,     setMessages]     = useState([WELCOME]);
  const [input,        setInput]        = useState('');
  const [loading,      setLoading]      = useState(false);
  const [sessionId,    setSessionId]    = useState(null);
  const [language,     setLanguage]     = useState('en');
  const [langOpen,     setLangOpen]     = useState(false);
  const [unread,       setUnread]       = useState(0);
  const [pulseBtn,     setPulseBtn]     = useState(true);

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  // Restore session
  useEffect(() => {
    const saved = localStorage.getItem(SESSION_KEY);
    if (saved) setSessionId(saved);
    else {
      const id = `em_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      setSessionId(id);
      localStorage.setItem(SESSION_KEY, id);
    }
    // Pulse button after 4s to draw attention
    const t = setTimeout(() => setPulseBtn(false), 6000);
    return () => clearTimeout(t);
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when opening
  useEffect(() => {
    if (open && !minimised) {
      setTimeout(() => inputRef.current?.focus(), 200);
      setUnread(0);
    }
  }, [open, minimised]);

  const addMsg = useCallback((msg) => {
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), ts: Date.now(), ...msg }]);
  }, []);

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    addMsg({ role: 'user', text: trimmed });
    setInput('');
    setLoading(true);

    // Typing indicator
    const typingId = `typing_${Date.now()}`;
    setMessages(prev => [...prev, { id: typingId, role: 'typing', text: '', ts: Date.now() }]);

    try {
      const { data } = await chatSendMessage({
        message: trimmed,
        session_id: sessionId,
        language,
      });

      // Remove typing indicator
      setMessages(prev => prev.filter(m => m.id !== typingId));

      addMsg({
        role: 'assistant',
        text: data.message || "I couldn't process that. Please try again.",
        suggestions: data.suggestions || [],
        intent: data.intent,
      });

      if (!open) setUnread(c => c + 1);

    } catch (err) {
      setMessages(prev => prev.filter(m => m.id !== typingId));
      addMsg({
        role: 'assistant',
        text: "Sorry, I had trouble connecting. Please check that the backend is running and try again.",
        suggestions: ['Apartment prices in Tunis?', 'Investment advice?'],
      });
    } finally {
      setLoading(false);
    }
  }, [loading, sessionId, language, open, addMsg]);

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleSuggestion = (s) => sendMessage(s);

  const handleReset = () => {
    const id = `em_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setSessionId(id);
    localStorage.setItem(SESSION_KEY, id);
    setMessages([WELCOME]);
  };

  const toggleOpen = () => {
    setOpen(o => !o);
    setMinimised(false);
  };

  return (
    <>
      {/* ── Keyframe injection ── */}
      <style>{`
        @keyframes chatBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes chatFadeUp {
          from { opacity: 0; transform: translateY(20px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes chatPulse {
          0%,100% { box-shadow: 0 0 0 0 rgba(255,107,53,0.7); }
          50%     { box-shadow: 0 0 0 14px rgba(255,107,53,0); }
        }
      `}</style>

      {/* ═══════════════════════════════════════════════
          Chat Popup
      ═══════════════════════════════════════════════ */}
      {open && (
        <div
          className="fixed bottom-24 right-5 z-[9998] flex flex-col"
          style={{
            width: 'min(420px, calc(100vw - 24px))',
            height: minimised ? 'auto' : 'min(640px, calc(100vh - 120px))',
            animation: 'chatFadeUp .22s ease forwards',
          }}>

          {/* Glass card */}
          <div className="flex flex-col h-full rounded-3xl overflow-hidden shadow-2xl"
            style={{ background: 'linear-gradient(145deg, #111827 0%, #0f172a 100%)', border: '1px solid rgba(255,255,255,0.10)' }}>

            {/* ── Header ── */}
            <div className="flex-shrink-0 flex items-center justify-between px-5 py-4"
              style={{ background: 'linear-gradient(135deg, #FF6B35 0%, #e55a2b 100%)' }}>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                  <Sparkles size={18} className="text-white" />
                </div>
                <div>
                  <p className="text-[13px] font-black text-white leading-tight">EstateMind AI</p>
                  <p className="text-[10px] text-orange-100/80 leading-tight">Real Estate Advisor · Tunisia</p>
                </div>
                <span className="ml-2 text-[10px] bg-white/20 text-white rounded-full px-2 py-0.5 font-semibold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-300 rounded-full animate-pulse inline-block"/>Online
                </span>
              </div>

              <div className="flex items-center gap-1">
                {/* Language */}
                <div className="relative">
                  <button onClick={() => setLangOpen(l => !l)}
                    className="flex items-center gap-1 text-[11px] text-white/80 bg-white/15 rounded-lg px-2 py-1 hover:bg-white/25 transition-colors">
                    <Globe2 size={11} />
                    {LANGS.find(l => l.code === language)?.label}
                    <ChevronDown size={9} />
                  </button>
                  {langOpen && (
                    <div className="absolute right-0 top-8 bg-[#1a2334] border border-white/10 rounded-xl overflow-hidden shadow-2xl z-10 w-32">
                      {LANGS.map(l => (
                        <button key={l.code}
                          onClick={() => { setLanguage(l.code); setLangOpen(false); }}
                          className={`w-full text-left px-3 py-2 text-xs transition-colors ${language === l.code ? 'text-[#FF6B35] bg-[#FF6B35]/10' : 'text-gray-300 hover:bg-white/5'}`}>
                          {l.label} · {l.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button onClick={handleReset} title="New chat"
                  className="w-7 h-7 rounded-xl bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors">
                  <RotateCcw size={12} className="text-white" />
                </button>
                <button onClick={() => setMinimised(m => !m)}
                  className="w-7 h-7 rounded-xl bg-white/15 hover:bg-white/25 flex items-center justify-center transition-colors">
                  <Minimize2 size={12} className="text-white" />
                </button>
                <button onClick={() => setOpen(false)}
                  className="w-7 h-7 rounded-xl bg-white/15 hover:bg-white/30 flex items-center justify-center transition-colors">
                  <X size={13} className="text-white" />
                </button>
              </div>
            </div>

            {!minimised && (
              <>
                {/* ── Quick actions ── */}
                <div className="flex-shrink-0 flex gap-2 px-4 py-2.5 overflow-x-auto"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', scrollbarWidth: 'none' }}>
                  {QUICK_ACTIONS.map(({ label, icon: Icon, q }) => (
                    <button key={label} onClick={() => handleSuggestion(q)}
                      className="flex items-center gap-1.5 text-[11px] text-gray-400 border border-white/10 bg-white/[0.04] rounded-full px-3 py-1.5 hover:border-[#FF6B35]/40 hover:text-[#FF6B35] transition-all flex-shrink-0">
                      <Icon size={11} />
                      {label}
                    </button>
                  ))}
                </div>

                {/* ── Messages ── */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
                  style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,107,53,0.3) transparent' }}>
                  {messages.map(msg => (
                    <MessageBubble key={msg.id} msg={msg} onSuggestion={handleSuggestion} />
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {/* ── Input ── */}
                <div className="flex-shrink-0 p-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <form onSubmit={handleSubmit} className="flex items-end gap-2">
                    <div className="flex-1 relative">
                      <textarea
                        ref={inputRef}
                        rows={1}
                        value={input}
                        onChange={e => {
                          setInput(e.target.value);
                          e.target.style.height = 'auto';
                          e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
                        }}
                        onKeyDown={e => {
                          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input); }
                        }}
                        placeholder="Ask about prices, investments, forecasts…"
                        disabled={loading}
                        className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white placeholder-gray-600 focus:border-[#FF6B35]/50 focus:outline-none focus:ring-1 focus:ring-[#FF6B35]/25 transition-all leading-snug"
                        style={{ minHeight: '44px', maxHeight: '100px' }}
                      />
                    </div>
                    <button type="submit" disabled={loading || !input.trim()}
                      className="w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 transition-all shadow-lg"
                      style={{
                        background: input.trim() && !loading
                          ? 'linear-gradient(135deg, #FF6B35, #e55a2b)'
                          : 'rgba(255,255,255,0.06)',
                        boxShadow: input.trim() && !loading ? '0 4px 15px rgba(255,107,53,0.4)' : 'none',
                      }}>
                      <Send size={14} className={input.trim() && !loading ? 'text-white' : 'text-gray-600'} />
                    </button>
                  </form>
                  <p className="text-[10px] text-gray-700 mt-1.5 text-center">
                    Powered by EstateMind AI · Real data from 278 delegations
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════
          FAB Button
      ═══════════════════════════════════════════════ */}
      <button
        onClick={toggleOpen}
        className="fixed bottom-5 right-5 z-[9999] w-14 h-14 rounded-2xl flex items-center justify-center shadow-2xl transition-all duration-200 hover:scale-110 active:scale-95"
        style={{
          background: open
            ? 'linear-gradient(135deg, #1f2937, #111827)'
            : 'linear-gradient(135deg, #FF6B35 0%, #e55a2b 100%)',
          boxShadow: open
            ? '0 8px 32px rgba(0,0,0,0.4)'
            : '0 8px 32px rgba(255,107,53,0.45)',
          animation: pulseBtn && !open ? 'chatPulse 2s ease-in-out infinite' : 'none',
          border: '1px solid rgba(255,255,255,0.15)',
        }}
        title={open ? 'Close chat' : 'AI Real Estate Advisor'}>
        {open
          ? <X size={20} className="text-gray-400" />
          : <MessageCircle size={22} className="text-white" />
        }
        {/* Unread badge */}
        {!open && unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-green-500 text-white text-[10px] font-black flex items-center justify-center border-2 border-[#0B0F19]">
            {unread}
          </span>
        )}
      </button>

      {/* Tooltip on first load */}
      {pulseBtn && !open && (
        <div className="fixed bottom-[76px] right-5 z-[9999] bg-[#1a2334] border border-white/10 rounded-2xl px-3 py-2 shadow-2xl pointer-events-none"
          style={{ animation: 'chatFadeUp .3s ease forwards' }}>
          <p className="text-xs font-semibold text-white whitespace-nowrap">AI Real Estate Advisor</p>
          <p className="text-[10px] text-gray-400">Ask me anything about Tunisia's market</p>
          <div className="absolute bottom-[-6px] right-5 w-3 h-3 bg-[#1a2334] border-r border-b border-white/10 rotate-45" />
        </div>
      )}
    </>
  );
}
