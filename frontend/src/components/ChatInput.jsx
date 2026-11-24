import React, { useRef, useEffect } from 'react';
import { Send, CornerDownLeft, Loader2 } from 'lucide-react';

export default function ChatInput({ input, setInput, onSend, isLoading }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && input.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="p-4 bg-dark-900/90 border-t border-slate-800 backdrop-blur-md">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end gap-2 bg-dark-950/80 rounded-2xl border border-slate-700/80 focus-within:border-emerald-500/80 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all p-2 shadow-inner">
          <textarea
            ref={textareaRef}
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Enter to send, Shift+Enter for newline)"
            rows={1}
            disabled={isLoading}
            className="flex-1 max-h-[180px] bg-transparent resize-none border-0 text-slate-100 placeholder-slate-500 text-sm md:text-base focus:outline-none px-3 py-2 leading-relaxed"
          />

          <button
            data-testid="send-button"
            onClick={onSend}
            disabled={isLoading || !input.trim()}
            className="flex-shrink-0 w-10 h-10 rounded-xl bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 disabled:hover:bg-emerald-500 text-white flex items-center justify-center transition-all shadow-md shadow-emerald-950/40 cursor-pointer disabled:cursor-not-allowed"
            title="Send message"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-4 h-4 ml-0.5" />
            )}
          </button>
        </div>

        <div className="flex items-center justify-between mt-2 px-2 text-[11px] text-slate-500">
          <span className="hidden sm:inline">Use Shift + Enter for new lines</span>
          <span>Max 4000 characters</span>
        </div>
      </div>
    </div>
  );
}

