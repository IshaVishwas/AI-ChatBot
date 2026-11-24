import React from 'react';
import { Bot, User, Zap, Database, Clock, ArrowDownCircle, ArrowUpCircle, ShieldCheck } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const meta = message.metadata || {};

  return (
    <div
      className={`flex gap-3 md:gap-4 p-4 md:p-6 transition-colors ${
        isUser ? 'bg-transparent' : 'bg-dark-900/40 border-y border-slate-800/40'
      }`}
      {...(!isUser ? { 'data-testid': 'assistant-message' } : {})}
    >
      {/* Avatar Icon */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center text-white shadow-md shadow-indigo-900/20">
            <User className="w-4 h-4" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-700 flex items-center justify-center text-white shadow-md shadow-emerald-900/20">
            <Bot className="w-4 h-4" />
          </div>
        )}
      </div>

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs md:text-sm text-slate-300">
            {isUser ? 'You' : 'Lyftr AI Assistant'}
          </span>
          <span className="text-[11px] text-slate-500">
            {message.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        {/* Content */}
        {isUser ? (
          <p className="text-sm md:text-base text-slate-200 whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        ) : (
          <MarkdownRenderer content={message.content} />
        )}

        {/* Assistant Metadata Row */}
        {!isUser && meta && (
          <div className="pt-2 mt-3 border-t border-slate-800/60">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {/* Resolution Source */}
              <div
                data-testid="meta-source"
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[11px] font-semibold tracking-wide ${
                  meta.resolution_source === 'LLM_CACHE'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                }`}
                title="Resolution Source"
              >
                {meta.resolution_source === 'LLM_CACHE' ? (
                  <>
                    <Database className="w-3 h-3" />
                    <span>LLM_CACHE</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-3 h-3" />
                    <span>LIVE_INFERENCE</span>
                  </>
                )}
              </div>

              {/* Model */}
              <div
                data-testid="meta-model"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[11px] bg-dark-850 text-slate-300 border border-slate-700/60"
                title="Model identifier"
              >
                <span className="text-slate-500">model:</span>
                <span>{meta.model || 'default'}</span>
              </div>

              {/* Latency */}
              <div
                data-testid="meta-latency"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[11px] bg-dark-850 text-slate-300 border border-slate-700/60"
                title="Server-side Latency"
              >
                <Clock className="w-3 h-3 text-slate-400" />
                <span>{meta.latency_ms !== undefined ? `${meta.latency_ms}ms` : '0ms'}</span>
              </div>

              {/* Input Tokens */}
              <div
                data-testid="meta-input-tokens"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[11px] bg-dark-850 text-slate-300 border border-slate-700/60"
                title="Input Tokens for this request"
              >
                <ArrowDownCircle className="w-3 h-3 text-blue-400" />
                <span>{meta.input_tokens !== undefined ? `${meta.input_tokens} in` : '0 in'}</span>
              </div>

              {/* Output Tokens */}
              <div
                data-testid="meta-output-tokens"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-[11px] bg-dark-850 text-slate-300 border border-slate-700/60"
                title="Output Tokens for this response"
              >
                <ArrowUpCircle className="w-3 h-3 text-emerald-400" />
                <span>{meta.output_tokens !== undefined ? `${meta.output_tokens} out` : '0 out'}</span>
              </div>

              {/* Key ID & Fallback Attempts Badge */}
              {meta.key_id ? (
                <div
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/30"
                  title="Serving API Key ID"
                >
                  <ShieldCheck className="w-3 h-3 text-purple-400" />
                  <span>{meta.key_id}</span>
                  {meta.fallback_attempts > 0 && (
                    <span className="ml-1 px-1 py-0.2 rounded bg-purple-500/30 text-purple-200 text-[10px]">
                      +{meta.fallback_attempts} fallback
                    </span>
                  )}
                </div>
              ) : meta.resolution_source === 'LLM_CACHE' ? (
                <div
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-400 border border-slate-700/50"
                  title="Cached key_id=null, fallback_attempts=0"
                >
                  <span>key: null</span>
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

