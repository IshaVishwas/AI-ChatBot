import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, AlertCircle, Sparkles, Loader2 } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';

export const getApiBase = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
      return 'http://localhost:8000';
    }
  }
  return 'https://ai-chatbot-xgce.onrender.com';
};

const API_BASE = getApiBase();
const STORAGE_KEY_SESSION = 'lyftr_active_session_id';

function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `session_${crypto.randomUUID().slice(0, 16)}`;
  }
  return `session_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function getStoredSessionId() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY_SESSION);
    if (saved && saved.trim()) {
      return saved.trim();
    }
  } catch (e) {
    console.warn('localStorage read error:', e);
  }
  return null;
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => {
    const saved = getStoredSessionId();
    if (saved) return saved;
    const fresh = generateSessionId();
    try {
      localStorage.setItem(STORAGE_KEY_SESSION, fresh);
    } catch (e) {}
    return fresh;
  });
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [health, setHealth] = useState(null);

  const messagesEndRef = useRef(null);

  // Helper to sync state and persistent storage
  const updateActiveSession = (newId) => {
    if (!newId) return;
    setSessionId(newId);
    try {
      localStorage.setItem(STORAGE_KEY_SESSION, newId);
    } catch (e) {
      console.warn('localStorage write error:', e);
    }
  };

  // Auto-scroll to latest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Fetch health status
  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.warn('Backend health check unreachable:', err);
    }
  };

  // Fetch all saved conversation sessions
  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      if (res.ok) {
        const data = await res.json();
        const list = data || [];
        setSessions(list);
        return list;
      }
    } catch (err) {
      console.warn('Failed to load chat history sessions:', err);
    }
    return [];
  };

  // Restore active session messages on startup / refresh
  const restoreSessionMessages = async (targetSessionId) => {
    if (!targetSessionId) return false;

    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE}/sessions/${targetSessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        const formatted = (data.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          metadata: m.metadata || null,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }));
        setMessages(formatted);
        return true;
      } else if (res.status === 404) {
        // Session has no persisted messages in database yet
        setMessages([]);
        return false;
      } else {
        console.warn(`Could not load messages for session ${targetSessionId}: HTTP ${res.status}`);
        return false;
      }
    } catch (err) {
      console.warn(`Network error restoring session ${targetSessionId}:`, err);
      return false;
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    const initialize = async () => {
      fetchHealth();

      const loadedSessions = await fetchSessions();
      if (!isMounted) return;

      const savedId = getStoredSessionId();
      let targetId = savedId;

      // If no saved session in localStorage, but sessions exist in database, restore the most recent conversation
      if (!targetId && loadedSessions && loadedSessions.length > 0) {
        targetId = loadedSessions[0].session_id;
        updateActiveSession(targetId);
      } else if (!targetId) {
        targetId = sessionId;
        updateActiveSession(targetId);
      }

      if (targetId) {
        await restoreSessionMessages(targetId);
      }
    };

    initialize();

    return () => {
      isMounted = false;
    };
  }, []);

  // Handle New Chat: generate fresh session_id, persist to storage, and clear message list
  const handleNewChat = () => {
    const newId = generateSessionId();
    updateActiveSession(newId);
    setMessages([]);
    setErrorMessage(null);
  };

  // Handle Selecting a Previous Conversation
  const handleSelectSession = async (selectedId) => {
    if (selectedId === sessionId && messages.length > 0) return;

    updateActiveSession(selectedId);
    setErrorMessage(null);
    await restoreSessionMessages(selectedId);
  };

  // Handle Deleting a Conversation
  const handleDeleteSession = async (idToDelete, event) => {
    event?.stopPropagation();
    if (!window.confirm('Delete this conversation history from database?')) return;

    try {
      const res = await fetch(`${API_BASE}/sessions/${idToDelete}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchSessions();
        // If current active session was deleted, start a new chat
        if (idToDelete === sessionId) {
          handleNewChat();
        }
      } else {
        setErrorMessage('Failed to delete conversation.');
      }
    } catch (err) {
      setErrorMessage('Network error while deleting conversation.');
    }
  };

  // Handle Send Message
  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setErrorMessage(null);
    const userMessage = {
      role: 'user',
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Append user message immediately
    setMessages((prev) => [...prev, userMessage]);
    // Clear input
    setInput('');
    setIsLoading(true);

    try {
      const payload = {
        session_id: sessionId,
        message: trimmed,
        ...(systemPrompt.trim() ? { system_prompt: systemPrompt.trim() } : {})
      };

      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = data.detail || `Server error (${response.status})`;
        setErrorMessage(detail);
        // Remove user message if not persisted
        setMessages((prev) => prev.slice(0, -1));
        return;
      }

      const assistantMessage = {
        role: 'assistant',
        content: data.reply,
        metadata: data.metadata,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Ensure active session is persisted in localStorage
      updateActiveSession(sessionId);

      // Refresh conversation list to display newly saved conversation or updated order
      await fetchSessions();
    } catch (err) {
      setErrorMessage(`Network error: Could not reach backend at ${API_BASE}. Make sure the server is running.`);
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-dark-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar with Chat History */}
      <Sidebar
        sessionId={sessionId}
        onNewChat={handleNewChat}
        sessions={sessions}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        systemPrompt={systemPrompt}
        setSystemPrompt={setSystemPrompt}
        health={health}
        onRefreshHealth={fetchHealth}
      />

      {/* Main Chat Workspace */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-dark-950 relative">
        {/* Top Header Bar */}
        <header className="h-14 border-b border-slate-800 bg-dark-900/60 backdrop-blur-md flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-semibold text-sm text-slate-200">Session:</span>
            <span className="font-mono text-xs text-slate-400 bg-dark-800 px-2 py-0.5 rounded border border-slate-700/60">
              {sessionId}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span>LiteLLM Multi-Key Gateway</span>
          </div>
        </header>

        {/* Error Notification Banner */}
        {errorMessage && (
          <div className="p-3 mx-4 mt-3 rounded-xl bg-red-950/60 border border-red-700/60 text-red-200 flex items-center justify-between text-sm shadow-lg animate-in fade-in slide-in-from-top duration-200">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-xs text-red-400 hover:text-red-200 underline cursor-pointer ml-3"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Chat Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingHistory ? (
            <div className="h-full flex flex-col items-center justify-center p-6 text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
              <p className="text-sm">Restoring active conversation...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-6 text-center text-slate-400 space-y-4 max-w-md mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/5">
                <Sparkles className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-lg text-slate-100">Welcome to Lyftr AI Chatbot</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Powered by LiteLLM gateway with automatic multi-key failover, sub-millisecond in-memory caching, and multi-turn persistence.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-2 w-full pt-2 text-left">
                {[
                  'What is the architecture of this AI chatbot?',
                  'Explain how LiteLLM automatic failover works.',
                  'Demonstrate cache hit behavior.'
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInput(prompt);
                    }}
                    className="p-2.5 rounded-xl bg-dark-900 border border-slate-800 hover:border-emerald-500/50 hover:bg-dark-850 text-xs text-slate-300 transition-all cursor-pointer text-left"
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/20">
              {messages.map((msg, idx) => (
                <ChatMessage key={idx} message={msg} />
              ))}

              {isLoading && (
                <div className="flex gap-4 p-6 bg-dark-900/40 border-y border-slate-800/40 animate-pulse">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <Sparkles className="w-4 h-4 animate-spin" />
                  </div>
                  <div className="space-y-2 flex-1">
                    <div className="h-4 bg-slate-800 rounded w-1/4"></div>
                    <div className="h-4 bg-slate-800/60 rounded w-3/4"></div>
                    <div className="h-4 bg-slate-800/40 rounded w-1/2"></div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat Input Bar */}
        <ChatInput
          input={input}
          setInput={setInput}
          onSend={handleSend}
          isLoading={isLoading || isLoadingHistory}
        />
      </main>
    </div>
  );
}
