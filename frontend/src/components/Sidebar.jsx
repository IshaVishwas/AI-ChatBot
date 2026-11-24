import React, { useState, useEffect } from 'react';
import {
  Plus,
  Sparkles,
  MessageSquare,
  History,
  Trash2,
  Sliders,
  Shield,
  RefreshCw,
  Clock
} from 'lucide-react';

export function parseUtcDate(dateStr) {
  if (!dateStr) return null;
  let str = String(dateStr).trim();
  // If string is an ISO format without timezone suffix (Z or +/-HH:MM),
  // append 'Z' because all stored database timestamps are UTC.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(str) && !/(Z|[+-]\d{2}(:?\d{2})?)$/i.test(str)) {
    str += 'Z';
  }
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
}

export function formatRelativeTime(dateStr, now = new Date()) {
  const d = parseUtcDate(dateStr);
  if (!d) return '';

  const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

  // Clock skew or created within the last 60 seconds
  if (diffSec < 60) return 'just now';

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHours = Math.floor(diffSec / 3600);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffSec / 86400);
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;

  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function Sidebar({
  sessionId,
  onNewChat,
  sessions = [],
  onSelectSession,
  onDeleteSession,
  systemPrompt,
  setSystemPrompt,
  health,
  onRefreshHealth
}) {
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const [, setTick] = useState(0);

  // Dynamically update relative timestamps every 30 seconds without page refresh
  useEffect(() => {
    const timer = setInterval(() => {
      setTick((t) => t + 1);
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <aside className="w-80 bg-dark-900 border-r border-slate-800 flex flex-col h-full select-none flex-shrink-0">
      {/* Branding Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center text-white shadow-lg shadow-emerald-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-extrabold text-base tracking-tight text-white flex items-center gap-1.5">
              Lyftr AI
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                v1.0
              </span>
            </h1>
            <p className="text-[11px] text-slate-400">Intelligent Gateway</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all shadow-md shadow-emerald-950/50 cursor-pointer active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* CHAT HISTORY Section */}
      <div className="flex-1 flex flex-col min-h-0 border-t border-slate-800/80">
        <div className="flex items-center justify-between px-4 pt-3 pb-2 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
          <span className="flex items-center gap-1.5">
            <History className="w-3.5 h-3.5 text-emerald-400" />
            Chat History
          </span>
          {sessions.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-dark-800 text-emerald-400 border border-emerald-500/20 font-mono text-[10px]">
              {sessions.length}
            </span>
          )}
        </div>

        {/* Scrollable Conversation List */}
        <div className="flex-1 overflow-y-auto px-3 space-y-1.5 py-1">
          {sessions.length === 0 ? (
            <div className="p-5 text-center text-slate-500 text-xs flex flex-col items-center justify-center gap-2 my-2 border border-dashed border-slate-800/80 rounded-xl bg-dark-950/40">
              <MessageSquare className="w-6 h-6 opacity-30 text-emerald-400" />
              <p className="font-semibold text-slate-300">No previous conversations yet.</p>
              <p className="text-[11px] text-slate-500 max-w-[180px] leading-relaxed">
                Your conversations will be automatically saved here.
              </p>
            </div>
          ) : (
            sessions.map((s) => {
              const isCurrent = s.session_id === sessionId;
              return (
                <div
                  key={s.session_id}
                  onClick={() => onSelectSession(s.session_id)}
                  className={`group relative flex items-center justify-between p-2.5 rounded-xl text-left cursor-pointer transition-all border ${
                    isCurrent
                      ? 'bg-dark-850 border-emerald-500/60 text-white shadow-md shadow-emerald-950/40'
                      : 'bg-dark-950/40 border-slate-800/60 text-slate-300 hover:bg-dark-850 hover:border-slate-700 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1 pr-2">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isCurrent ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-slate-600 group-hover:bg-slate-500'}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold truncate leading-snug" title={s.title}>
                        {s.title || s.session_id}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-1 font-mono">
                        {s.updated_at && <span>{formatRelativeTime(s.updated_at)}</span>}
                        {s.updated_at && <span>•</span>}
                        <span>{s.message_count} msgs</span>
                      </div>
                    </div>
                  </div>

                  {/* Inline Delete Button */}
                  <button
                    onClick={(e) => onDeleteSession(s.session_id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all flex-shrink-0 cursor-pointer"
                    title="Delete conversation"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* System Prompt Toggle & Input */}
      <div className="px-4 py-2 border-t border-slate-800/80 bg-dark-950/30">
        <button
          onClick={() => setShowSystemPrompt(!showSystemPrompt)}
          className="flex items-center justify-between w-full text-xs text-slate-300 hover:text-emerald-400 transition-colors py-1.5 cursor-pointer"
        >
          <span className="flex items-center gap-1.5 font-semibold">
            <Sliders className="w-3.5 h-3.5 text-emerald-400" />
            System Prompt
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-dark-800 text-slate-400">
            {showSystemPrompt ? 'Hide' : 'Configure'}
          </span>
        </button>

        {showSystemPrompt && (
          <div className="mt-2 space-y-1.5 pb-2">
            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="E.g.: You are an expert AI engineer..."
              rows={3}
              className="w-full p-2 bg-dark-950 border border-slate-700/80 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 resize-none font-sans"
            />
            <p className="text-[10px] text-slate-500">
              Steers responses for current session.
            </p>
          </div>
        )}
      </div>

      {/* Gateway Health Status */}
      <div className="p-3 border-t border-slate-800 bg-dark-950/60">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
          <span className="flex items-center gap-1.5 font-medium">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            Gateway Status
          </span>
          <button
            onClick={onRefreshHealth}
            className="text-slate-500 hover:text-slate-300 p-1 rounded cursor-pointer"
            title="Refresh health status"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        {health ? (
          <div className="space-y-1 text-[11px] font-mono">
            <div className="flex items-center justify-between text-slate-400">
              <span>Status:</span>
              <span className="text-emerald-400 font-semibold">{health.status}</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>Keys Pool:</span>
              <span className="text-slate-200">{health.keys_configured} keys</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>Cache:</span>
              <span className={health.cache_enabled ? 'text-emerald-400' : 'text-slate-500'}>
                {health.cache_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-slate-500 italic">Checking health...</p>
        )}
      </div>
    </aside>
  );
}
