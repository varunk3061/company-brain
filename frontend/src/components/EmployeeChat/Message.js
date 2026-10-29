"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BrainIcon, FileIcon } from "./icons";
import { getDocumentViewUrl } from "@/services/documentService";

// Answers are Markdown (tables, lists, bold). react-markdown never renders raw HTML, so model
// output cannot inject markup. Every element is styled with theme tokens only.
// `md` builds one element renderer; it drops react-markdown's `node` prop so it never reaches the DOM.
const md = (Tag, className, extra = {}) =>
  function MarkdownElement({ node: _node, ...props }) {
    return <Tag className={className} {...extra} {...props} />;
  };

const MARKDOWN_COMPONENTS = {
  strong: md("strong", "font-semibold text-ink"),
  ul: md("ul", "list-disc space-y-1 pl-5"),
  ol: md("ol", "list-decimal space-y-1 pl-5"),
  h1: md("h3", "font-semibold text-ink"),
  h2: md("h3", "font-semibold text-ink"),
  h3: md("h3", "font-semibold text-ink"),
  table: function MarkdownTable({ node: _node, ...props }) {
    return (
      <div className="overflow-x-auto rounded-control border border-line">
        <table className="w-full text-left text-sm" {...props} />
      </div>
    );
  },
  thead: md("thead", "bg-surface-2 text-ink"),
  th: md("th", "px-3 py-2 font-semibold"),
  td: md("td", "border-t border-line px-3 py-2 align-top"),
  a: md("a", "text-brand-text underline", { target: "_blank", rel: "noopener noreferrer" }),
};

const LIST_ITEM = /^([-*+]|\d+\.)\s/;

// Saved conversations store the answer as trimmed lines. Re-join them so consecutive table rows
// and list items stay together, and everything else stays a separate paragraph.
function paragraphsToMarkdown(paragraphs = []) {
  return paragraphs.reduce((text, line, i) => {
    if (i === 0) return line;
    const prev = paragraphs[i - 1];
    const sameBlock =
      (prev.startsWith("|") && line.startsWith("|")) ||
      (LIST_ITEM.test(prev) && LIST_ITEM.test(line));
    return text + (sameBlock ? "\n" : "\n\n") + line;
  }, "");
}

// A cited document. Clicking asks the backend for a short-lived link (issued only if this user may
// read the document) and opens the original PDF in a new tab. The browser never holds storage keys.
function CitationCard({ source }) {
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const canOpen = Boolean(source.document_uuid);

  const open = async () => {
    if (!canOpen || opening) return;

    // Open the tab inside the click so pop-up blockers allow it, then point it at the link.
    const tab = window.open("", "_blank");
    if (tab) tab.opener = null;

    setOpening(true);
    setError("");

    try {
      const { url } = await getDocumentViewUrl(source.document_uuid);
      if (tab) tab.location.replace(url);
      else window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      tab?.close();
      setError(
        err.message === "Document not found."
          ? "This document is no longer available to you."
          : err.message || "Could not open the document.",
      );
    } finally {
      setOpening(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={open}
        disabled={!canOpen || opening}
        title={canOpen ? "Open the PDF in a new tab" : undefined}
        className="flex w-full items-center gap-3 rounded-control border border-line bg-surface-2 px-4 py-3 text-left transition hover:border-brand/30 hover:bg-brand-tint/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-default"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-danger-soft text-danger">
          <FileIcon className="h-4.5 w-4.5" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-ink">{source.file}</span>
          <span className="block text-xs text-ink-3">
            Page {source.page ?? "Unknown"}
            {canOpen && (
              <span className="text-brand-text"> · {opening ? "Opening..." : "View PDF"}</span>
            )}
          </span>
        </span>
      </button>
      {error && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

function BotAvatar() {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-on-brand shadow-card">
      <BrainIcon className="h-5 w-5" />
    </div>
  );
}

export function UserMessage({ message, initials }) {
  return (
    <div className="flex items-start justify-end gap-3">
      <div className="max-w-4/5 rounded-card rounded-tr-md bg-brand px-5 py-3.5 text-chat leading-relaxed text-on-brand shadow-card sm:max-w-7/10">
        {message.text}
      </div>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-on-brand">
        {initials}
      </div>
    </div>
  );
}

export function AssistantMessage({ message }) {
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className="flex items-start gap-3">
      <BotAvatar />
      <div className="w-full max-w-3xl rounded-card rounded-tl-md border border-line bg-surface p-5 shadow-card">
        <div className="space-y-3 text-chat leading-relaxed text-ink-2">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
            {message.text ?? paragraphsToMarkdown(message.paragraphs)}
          </ReactMarkdown>
        </div>

        {hasSources && (
          <div className="mt-5 border-t border-line pt-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-3">
              Retrieved document citations (RAG engine)
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {message.sources.map((s, i) => {
                const docName = s.file || s.source || s.fileName || "Unknown document";
                return (
                  <div
                    key={`${docName}-${s.page}-${i}`}
                    className="flex items-center gap-3 rounded-control border border-line bg-surface-2 px-4 py-3 transition hover:border-brand/30 hover:bg-brand-tint/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-danger-soft text-danger">
                      <FileIcon className="h-4.5 w-4.5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-ink">{docName}</span>
                      <span className="block text-xs text-ink-3">
                        Page {s.page ?? "Unknown"}
                      </span>
                    </span>
                  </div>
                );
              })}
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
      <div className="flex items-center gap-1.5 rounded-card rounded-tl-md border border-line bg-surface px-5 py-4 shadow-card">
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong anim-delay-1" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong anim-delay-2" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong" />
      </div>
    </div>
  );
}
