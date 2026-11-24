import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export default function MarkdownRenderer({ content }) {
  if (!content) return null;

  // Split content by code fences ```
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-3 leading-relaxed text-sm md:text-base text-slate-200">
      {parts.map((part, index) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const firstLine = lines[0].trim();
          const hasLang = firstLine && !firstLine.includes(' ') && lines.length > 1;
          const language = hasLang ? firstLine : '';
          const code = hasLang ? lines.slice(1).join('\n') : lines.join('\n');

          return <CodeBlock key={index} code={code} language={language} />;
        }

        // Render standard paragraphs and inline formatting
        const paragraphs = part.split(/\n\n+/);
        return paragraphs.map((para, pIdx) => {
          if (!para.trim()) return null;

          // Check if paragraph is list
          if (para.trim().startsWith('- ') || para.trim().startsWith('* ')) {
            const listItems = para.trim().split('\n');
            return (
              <ul key={`${index}-${pIdx}`} className="list-disc list-inside space-y-1.5 my-2 text-slate-300">
                {listItems.map((item, itemIdx) => (
                  <li key={itemIdx}>{renderInline(item.replace(/^[-*]\s+/, ''))}</li>
                ))}
              </ul>
            );
          }

          // Check for blockquote
          if (para.trim().startsWith('> ')) {
            return (
              <blockquote key={`${index}-${pIdx}`} className="border-l-4 border-emerald-500/50 pl-3 py-1 my-2 text-slate-400 italic bg-dark-900/40 rounded-r">
                {renderInline(para.replace(/^>\s+/, ''))}
              </blockquote>
            );
          }

          // Check for headers
          if (para.startsWith('### ')) {
            return <h3 key={`${index}-${pIdx}`} className="text-base font-bold text-emerald-400 mt-3 mb-1">{renderInline(para.slice(4))}</h3>;
          }
          if (para.startsWith('## ')) {
            return <h2 key={`${index}-${pIdx}`} className="text-lg font-bold text-slate-100 mt-4 mb-2">{renderInline(para.slice(3))}</h2>;
          }
          if (para.startsWith('# ')) {
            return <h1 key={`${index}-${pIdx}`} className="text-xl font-extrabold text-slate-100 mt-4 mb-2">{renderInline(para.slice(2))}</h1>;
          }

          return (
            <p key={`${index}-${pIdx}`} className="my-1.5 whitespace-pre-line">
              {renderInline(para)}
            </p>
          );
        });
      })}
    </div>
  );
}

function CodeBlock({ code, language }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-slate-700/60 bg-dark-950 font-mono text-xs md:text-sm shadow-md">
      <div className="flex items-center justify-between px-3 py-1.5 bg-dark-900/80 border-b border-slate-700/60 text-slate-400">
        <span className="uppercase text-[11px] font-semibold tracking-wider text-slate-400">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded text-xs hover:text-slate-200 hover:bg-slate-700/40 transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 text-[11px]">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[11px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="p-3.5 overflow-x-auto text-emerald-300">
        <pre><code>{code}</code></pre>
      </div>
    </div>
  );
}

function renderInline(text) {
  if (!text) return '';

  // Match inline backtick code `code`
  const codeParts = text.split(/(`[^`]+`)/g);

  return codeParts.map((cPart, cIdx) => {
    if (cPart.startsWith('`') && cPart.endsWith('`')) {
      return (
        <code key={cIdx} className="px-1.5 py-0.5 mx-0.5 rounded bg-dark-900 border border-slate-700 text-emerald-400 font-mono text-xs">
          {cPart.slice(1, -1)}
        </code>
      );
    }

    // Match bold **text**
    const boldParts = cPart.split(/(\*\*[^*]+\*\*)/g);
    return boldParts.map((bPart, bIdx) => {
      if (bPart.startsWith('**') && bPart.endsWith('**')) {
        return <strong key={`${cIdx}-${bIdx}`} className="font-semibold text-slate-100">{bPart.slice(2, -2)}</strong>;
      }
      return bPart;
    });
  });
}

