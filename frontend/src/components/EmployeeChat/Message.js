"use client";

import { BrainIcon, FileIcon } from "./icons";
import { USER } from "./data";

// Supports **bold** and [[file-name.pdf]] links inside answer text.
function renderInline(text) {
  return text
    .split(/(\*\*[^*]+\*\*|\[\[[^\]]+\]\])/g)
    .filter(Boolean)
    .map((part, i) => {
      if (part.startsWith("**")) {
        return (
          <strong key={i} className="font-semibold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("[[")) {
        return (
          <a
            key={i}
            href="#"
            onClick={(e) => e.preventDefault()}
            className="font-semibold text-indigo-600 hover:underline"
          >
            {part.slice(2, -2)}
          </a>
        );
      }
      return part;
    });
}

function BotAvatar() {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white shadow-sm">
      <BrainIcon className="h-5 w-5" />
    </div>
  );
}

export function UserMessage({ message }) {
  return (
    <div className="flex items-start justify-end gap-3">
      <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-indigo-600 px-5 py-3.5 text-[15px] leading-relaxed text-white shadow-md shadow-indigo-200/70 sm:max-w-[70%]">
        {message.text}
      </div>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-500 text-xs font-bold text-white">
        {USER.initials}
      </div>
    </div>
  );
}

export function AssistantMessage({ message }) {
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className="flex items-start gap-3">
      <BotAvatar />
      <div className="w-full max-w-3xl rounded-2xl rounded-tl-md border border-slate-200 bg-white p-5 shadow-sm">
        <div className="space-y-3 text-[15px] leading-relaxed text-slate-700">
          {message.paragraphs.map((p, i) => (
            <p key={i}>{renderInline(p)}</p>
          ))}
        </div>

        {hasSources && (
          <div className="mt-5 border-t border-slate-100 pt-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Retrieved document citations (RAG engine)
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {message.sources.map((s) => (
                <a
                  key={s.file}
                  href="#"
                  onClick={(e) => e.preventDefault()}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition hover:border-indigo-200 hover:bg-indigo-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-500">
                    <FileIcon className="h-[18px] w-[18px]" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-800">{s.file}</span>
                    <span className="block text-xs text-slate-500">
                      Relevance: {s.relevance}% &bull; Page {s.page}
                    </span>
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function TypingMessage() {
  return (
    <div className="flex items-start gap-3" role="status" aria-label="The Company Brain is searching">
      <BotAvatar />
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-md border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.3s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.15s]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-300" />
      </div>
    </div>
  );
}