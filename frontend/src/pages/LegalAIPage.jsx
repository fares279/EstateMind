import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Scale, Send, ExternalLink, ChevronRight,
  AlertCircle, CheckCircle2, Loader2, Sparkles,
  Receipt, Building2, BookOpen, Landmark, ArrowRight, RotateCcw,
} from 'lucide-react';
import { askLegalQuestion, getLegalStatus, getLegalSampleQuestions } from '../services/api';

// ─── Status chip ──────────────────────────────────────────────────────────────
function StatusChip({ s }) {
  if (!s) return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-gray-500">
      <Loader2 size={10} className="animate-spin" /> Connecting
    </span>
  );
  if (s.ready) return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      Ready
    </span>
  );
  if (!s.llm_available) return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-red-400">
      <AlertCircle size={10} /> Offline
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-amber-400">
      <Loader2 size={10} className="animate-spin" /> Initializing
    </span>
  );
}

// ─── Source card ──────────────────────────────────────────────────────────────
function SourceCard({ source, index }) {
  const hasLink = source.source_url && !source.source_url.startsWith('[');
  const Tag = hasLink ? 'a' : 'div';
  return (
    <Tag
      {...(hasLink ? { href: source.source_url, target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/[0.04] border border-white/[0.07] hover:bg-white/[0.07] hover:border-[#FF6B35]/20 transition-all group"
    >
      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[#FF6B35]/15 flex items-center justify-center text-[9px] font-bold text-[#FF6B35]">
        {index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium text-gray-300 truncate">{source.article_ref || `Article ${index + 1}`}</p>
        <p className="text-[10px] text-gray-600 truncate">{source.law_name}</p>
      </div>
      {hasLink && (
        <ExternalLink size={9} className="flex-shrink-0 text-gray-700 group-hover:text-[#FF6B35]/60 transition-colors" />
      )}
    </Tag>
  );
}

// ─── Message ──────────────────────────────────────────────────────────────────
function Message({ msg }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = msg.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[76%] text-white text-sm leading-relaxed rounded-2xl rounded-tr-sm px-4 py-3 shadow-lg"
          style={{ background: 'linear-gradient(135deg, #FF6B35, #e0541f)', boxShadow: '0 4px 20px rgba(255,107,53,0.15)' }}>
          {msg.content}
        </div>
      </div>
    );
  }

  const hasSources = msg.sources && msg.sources.length > 0;

  return (
    <div className="flex gap-3 items-start">
      <div className="flex-shrink-0 mt-1 w-8 h-8 rounded-xl bg-[#FF6B35]/10 border border-[#FF6B35]/20 flex items-center justify-center">
        <Scale size={14} className="text-[#FF6B35]" />
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="rounded-2xl rounded-tl-sm px-4 py-3.5"
          style={{ background: '#111827', border: '1px solid rgba(255,255,255,0.07)' }}>
          {msg.error ? (
            <div className="flex items-start gap-2.5">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5 text-red-400" />
              <div>
                <p className="text-sm font-medium text-red-300">Request failed</p>
                <p className="text-xs text-red-400/70 mt-1 leading-relaxed">{msg.error}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
          )}
        </div>

        {hasSources && (
          <div className="ml-1">
            <button
              onClick={() => setShowSources(v => !v)}
              className="inline-flex items-center gap-1.5 text-[11px] text-gray-600 hover:text-gray-400 transition-colors group"
            >
              <ChevronRight
                size={11}
                className={`transition-transform duration-200 ${showSources ? 'rotate-90' : ''}`}
              />
              <span className="font-medium text-gray-500 group-hover:text-gray-300">
                {msg.sources.length} source{msg.sources.length !== 1 ? 's' : ''}
              </span>
              <span className="text-gray-700">referenced</span>
            </button>
            {showSources && (
              <div className="mt-2 pl-3 border-l-2 border-[#FF6B35]/15 space-y-1.5">
                {msg.sources.map((s, i) => <SourceCard key={i} source={s} index={i} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Thinking indicator ───────────────────────────────────────────────────────
function Thinking() {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex-shrink-0 mt-1 w-8 h-8 rounded-xl bg-[#FF6B35]/10 border border-[#FF6B35]/20 flex items-center justify-center">
        <Scale size={14} className="text-[#FF6B35]" />
      </div>
      <div className="rounded-2xl rounded-tl-sm px-4 py-3.5"
        style={{ background: '#111827', border: '1px solid rgba(255,255,255,0.07)' }}>
        <div className="flex items-center gap-1.5">
          {[0, 160, 320].map(d => (
            <span
              key={d}
              className="w-1.5 h-1.5 rounded-full bg-gray-600 animate-bounce"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Quick-topic cards ────────────────────────────────────────────────────────
const QUICK_TOPICS = [
  {
    icon: Receipt,
    label: 'Registration & Duties',
    desc: 'Fees for property transactions',
    q: 'What registration duties apply to real estate transactions in Tunisia?',
  },
  {
    icon: Building2,
    label: 'Investment Incentives',
    desc: 'Benefits for real estate projects',
    q: 'What investment incentives are available for real estate projects in Tunisia?',
  },
  {
    icon: BookOpen,
    label: 'Property Taxation',
    desc: 'Income tax on real estate',
    q: 'How is income from real estate taxed under Tunisian law?',
  },
  {
    icon: Landmark,
    label: 'Company Formation',
    desc: 'Setting up a real estate company',
    q: 'What are the legal steps to create a real estate company in Tunisia?',
  },
];

// ─── Empty state ──────────────────────────────────────────────────────────────
function EmptyState({ questions, onAsk, status }) {
  const extraQuestions = questions.slice(4);

  return (
    <div className="flex flex-col items-center justify-center h-full gap-10 py-8 px-2">
      {/* Hero */}
      <div className="text-center space-y-3 max-w-lg">
        <div className="relative inline-flex mb-1">
          <div className="absolute inset-0 rounded-2xl blur-2xl scale-150" style={{ background: 'rgba(255,107,53,0.12)' }} />
          <div className="relative w-14 h-14 rounded-2xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, rgba(255,107,53,0.18), rgba(255,107,53,0.05))', border: '1px solid rgba(255,107,53,0.22)' }}>
            <Scale size={24} className="text-[#FF6B35]" />
          </div>
        </div>
        <h2 className="text-[26px] font-bold text-white tracking-tight">Legal AI Assistant</h2>
        <p className="text-gray-400 text-sm leading-relaxed">
          Instant answers on Tunisian real estate, corporate, and tax law.<br />
          Grounded in official legal texts.
        </p>
      </div>

      {/* Quick topic cards */}
      <div className="w-full max-w-2xl space-y-3">
        <p className="text-[10px] font-semibold text-gray-700 uppercase tracking-widest text-center">
          Quick topics
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {QUICK_TOPICS.map(({ icon: Icon, label, desc, q }, i) => (
            <button
              key={i}
              onClick={() => onAsk(q)}
              className="group flex items-center gap-3 text-left rounded-2xl px-4 py-3.5 transition-all duration-200"
              style={{ background: '#0F1420', border: '1px solid rgba(255,255,255,0.07)' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,107,53,0.22)'; e.currentTarget.style.background = '#141926'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; e.currentTarget.style.background = '#0F1420'; }}
            >
              <span className="flex-shrink-0 w-9 h-9 rounded-xl bg-[#FF6B35]/10 group-hover:bg-[#FF6B35]/18 flex items-center justify-center transition-colors">
                <Icon size={16} className="text-[#FF6B35]" />
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-gray-300 group-hover:text-white transition-colors">{label}</p>
                <p className="text-[11px] text-gray-600 group-hover:text-gray-500 mt-0.5 transition-colors">{desc}</p>
              </div>
              <ArrowRight size={12} className="flex-shrink-0 text-gray-700 group-hover:text-[#FF6B35]/50 group-hover:translate-x-0.5 transition-all" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function LegalAIPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [inputFocused, setInputFocused] = useState(false);

  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    getLegalStatus()
      .then(r => setStatus(r.data))
      .catch(() => setStatus({ ready: false, llm_available: false, documents_indexed: 0, model: 'Llama 3.1 70B' }));
    getLegalSampleQuestions()
      .then(r => setQuestions(r.data.questions || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
    }
  }, [input]);

  const send = useCallback(async (question) => {
    const q = (question ?? input).trim();
    if (!q || loading) return;

    setInput('');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: q }]);
    setLoading(true);

    try {
      const res = await askLegalQuestion(q);
      const { answer, sources } = res.data;
      setMessages(prev => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', content: answer, sources: sources || [] },
      ]);
      getLegalStatus().then(r => setStatus(r.data)).catch(() => {});
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        (err.code === 'ECONNABORTED'
          ? 'Request timed out. The model is taking longer than expected.'
          : 'Could not connect to the legal service.');
      setMessages(prev => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', content: '', error: errMsg, sources: [] },
      ]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }, [input, loading]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const modelLabel = status?.model
    ? status.model.replace('hosted_vllm/', '')
    : 'Llama 3.1 70B';

  const hasChat = messages.length > 0;
  const canSend = input.trim() && !loading;

  return (
    <div className="h-screen flex flex-col" style={{ background: '#080D18' }}>
      {/* Navbar clearance */}
      <div className="h-16 flex-shrink-0" />

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden flex flex-col max-w-3xl mx-auto w-full px-5">

        {/* Messages / empty state */}
        <div
          className="flex-1 overflow-y-auto"
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.05) transparent' }}
        >
          {!hasChat ? (
            <EmptyState questions={questions} onAsk={send} status={status} />
          ) : (
            <div className="py-8 space-y-5">
              {messages.map(m => <Message key={m.id} msg={m} />)}
              {loading && <Thinking />}
              <div ref={bottomRef} />
            </div>
          )}
          {hasChat && !loading && <div ref={bottomRef} />}
        </div>

        {/* ── Input bar ──────────────────────────────────────────────────── */}
        <div className="flex-shrink-0 pb-5 pt-3">
          <div
            className="flex items-end gap-3 rounded-2xl px-4 py-3 transition-all duration-200"
            style={{
              background: inputFocused ? 'rgba(255,255,255,0.055)' : 'rgba(255,255,255,0.04)',
              border: inputFocused ? '1px solid rgba(255,107,53,0.28)' : '1px solid rgba(255,255,255,0.09)',
            }}
          >
            <Sparkles size={14} className="flex-shrink-0 text-gray-600 mb-0.5 mt-0.5" />
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              placeholder="Ask a legal question about Tunisian law…"
              rows={1}
              style={{ resize: 'none', overflow: 'hidden' }}
              className="flex-1 bg-transparent text-white placeholder-gray-600 text-sm outline-none min-h-[22px] max-h-[120px] leading-relaxed"
            />
            <button
              onClick={() => send()}
              disabled={!canSend}
              className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 disabled:cursor-not-allowed"
              style={{
                background: canSend ? 'linear-gradient(135deg, #FF6B35, #e0541f)' : 'rgba(255,255,255,0.06)',
                color: canSend ? '#fff' : '#6b7280',
                boxShadow: canSend ? '0 4px 16px rgba(255,107,53,0.25)' : 'none',
              }}
            >
              {loading
                ? <Loader2 size={13} className="animate-spin" />
                : <Send size={13} />
              }
            </button>
          </div>
          <p className="text-center mt-2" style={{ fontSize: '10px', color: '#374151' }}>
            Enter to send · Shift+Enter for new line · Grounded in official Tunisian legal texts
          </p>
        </div>
      </div>
    </div>
  );
}
