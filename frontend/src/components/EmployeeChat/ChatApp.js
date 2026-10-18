
"use client";

import { getMyProfile } from "@/services/employeeService";
import { useEffect, useRef, useState } from "react";

import Sidebar from "./Sidebar";
import {
  AssistantMessage,
  TypingMessage,
  UserMessage,
} from "./Message";

import {
  BrainIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  DownloadIcon,
  LogOutIcon,
  MenuIcon,
  PaperclipIcon,
  SendIcon,
} from "./icons";

import {
  INITIAL_CONVERSATIONS,
  SCOPES,
  SUGGESTIONS,
  USER,
} from "./data";

const uid = () => Math.random().toString(36).slice(2, 10);

// Temporary mock response.
// We will replace this with your actual RAG API later.
async function askBrain(query, scope) {
  await new Promise((resolve) => setTimeout(resolve, 1200));

  return {
    id: uid(),
    role: "assistant",
    paragraphs: [
      `This is a placeholder answer for "${query}" (scope: ${scope}). Connect askBrain() to your backend to return real answers with document citations.`,
    ],
    sources: [],
  };
}

export default function ChatApp() {
  const [conversations, setConversations] = useState(
    INITIAL_CONVERSATIONS
  );

  const [activeId, setActiveId] = useState(
    INITIAL_CONVERSATIONS[0]?.id ?? null
  );

  const [scope, setScope] = useState(SCOPES[0]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Logged-in employee profile from FastAPI.
  const [employee, setEmployee] = useState(null);
  const [profileError, setProfileError] = useState("");

  const bottomRef = useRef(null);
  const menuRef = useRef(null);

  // Load the logged-in employee's profile.
  useEffect(() => {
    let cancelled = false;

    async function loadEmployeeProfile() {
      try {
        const profile = await getMyProfile();

        if (!cancelled) {
          setEmployee(profile);
          setProfileError("");
        }
      } catch (error) {
        if (!cancelled) {
          setProfileError(
            error.message || "Unable to load employee profile."
          );
        }
      }
    }

    loadEmployeeProfile();

    return () => {
      cancelled = true;
    };
  }, []);

  // Automatically scroll to the latest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [
    conversations,
    loading,
    activeId,
  ]);

  // Close the profile menu when clicking outside it.
  useEffect(() => {
    const onClick = (event) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target)
      ) {
        setMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", onClick);

    return () => {
      document.removeEventListener("mousedown", onClick);
    };
  }, []);

  // Resolve the active conversation.
  const active =
    conversations.find((conversation) => conversation.id === activeId) ??
    null;

  const messages = active?.messages ?? [];

  const hasSources = messages.some(
    (message) => message.sources?.length > 0
  );

  // Use the API profile, falling back to the existing mock data.
  const employeeName =
    employee?.name || USER.name || "Employee";

  const employeeRole =
    employee?.role || USER.role || "Employee";

  const employeeInitials = employeeName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

  // Start a new conversation.
  const handleNew = () => {
    setActiveId(null);
    setInput("");
    setSidebarOpen(false);
  };

  // Select an existing conversation.
  const handleSelect = (id) => {
    setActiveId(id);
    setSidebarOpen(false);
  };

  // Send a message and display the response.
  const send = async (text) => {
    const query = text.trim();

    if (!query || loading) return;

    const userMsg = {
      id: uid(),
      role: "user",
      text: query,
    };

    let convId = activeId;

    if (!convId) {
      convId = uid();

      const num =
        Math.max(0, ...conversations.map((conversation) => conversation.num)) +
        1;

      const title =
        query.length > 40
          ? `${query.slice(0, 40)}...`
          : query;

      setConversations((previous) => [
        {
          id: convId,
          num,
          title,
          messages: [userMsg],
        },
        ...previous,
      ]);

      setActiveId(convId);
    } else {
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === convId
            ? {
                ...conversation,
                messages: [
                  ...conversation.messages,
                  userMsg,
                ],
              }
            : conversation
        )
      );
    }

    setInput("");
    setLoading(true);

    try {
      const reply = await askBrain(query, scope);

      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === convId
            ? {
                ...conversation,
                messages: [
                  ...conversation.messages,
                  reply,
                ],
              }
            : conversation
        )
      );
    } catch (error) {
      const errorReply = {
        id: uid(),
        role: "assistant",
        paragraphs: [
          error.message || "Something went wrong. Please try again.",
        ],
        sources: [],
      };

      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === convId
            ? {
                ...conversation,
                messages: [
                  ...conversation.messages,
                  errorReply,
                ],
              }
            : conversation
        )
      );
    } finally {
      setLoading(false);
    }
  };

  // Handle chat form submission.
  const handleSubmit = (event) => {
    event.preventDefault();
    send(input);
  };

  // Export the active conversation as Markdown.
  const handleExport = () => {
    if (!active) return;

    const lines = [`# ${active.title}`, ""];

    active.messages.forEach((message) => {
      if (message.role === "user") {
        lines.push(
          `**${employeeName}:** ${message.text}`,
          ""
        );
      } else {
        lines.push(
          `**The Company Brain:** ${message.paragraphs
            .join("\n\n")
            .replace(/\[\[|\]\]/g, "")}`,
          ""
        );

        message.sources?.forEach((source) =>
          lines.push(
            `- ${source.file} (relevance ${source.relevance}%, page ${source.page})`
          )
        );

        lines.push("");
      }
    });

    const blob = new Blob([lines.join("\n")], {
      type: "text/markdown",
    });

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = `${active.title
      .replace(/[^\w]+/g, "-")
      .toLowerCase()}.md`;

    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white text-slate-900">
      {/* Header */}
      <header className="relative z-40 flex h-18 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label="Toggle sidebar"
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 lg:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>

          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-200">
            <BrainIcon className="h-5 w-5" />
          </div>

          <span className="text-lg font-bold tracking-tight">
            The Company Brain
          </span>

          <span className="hidden rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[11px] font-medium text-indigo-700 sm:inline">
            Employee Knowledge RAG
          </span>
        </div>

        {/* Employee profile menu */}
        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex items-center gap-3 rounded-xl px-2 py-1.5 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              {employeeInitials}
            </span>

            <span className="hidden text-left leading-tight sm:block">
              <span className="block text-sm font-semibold text-slate-800">
                {employeeName}
              </span>

              <span className="block text-xs text-slate-500">
                {employeeRole}
              </span>
            </span>

            <ChevronDownIcon className="h-4 w-4 text-slate-400" />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
            >
              {profileError && (
                <p className="px-3 py-2 text-xs text-red-600">
                  {profileError}
                </p>
              )}

              <a
                href="/login"
                role="menuitem"
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                <LogOutIcon className="h-4 w-4 text-slate-500" />
                Sign out
              </a>
            </div>
          )}
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        {/* Mobile overlay */}
        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-20 bg-slate-900/30 lg:hidden"
          />
        )}

        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={handleSelect}
          onNew={handleNew}
          scope={scope}
          onScopeChange={setScope}
          open={sidebarOpen}
        />

        {/* Main chat area */}
        <main className="flex min-w-0 flex-1 flex-col bg-slate-50">
          {/* Profile error, if the API call fails */}
          {profileError && (
            <p
              role="alert"
              className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
            >
              Unable to load your profile: {profileError}
            </p>
          )}

          {/* Conversation title bar */}
          <div className="flex h-15 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <h1 className="truncate text-base font-semibold text-slate-900">
                {active?.title ?? "New knowledge query"}
              </h1>

              {hasSources && (
                <span className="hidden shrink-0 items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 sm:inline-flex">
                  <CheckCircleIcon className="h-3.5 w-3.5" />
                  Verified Sources
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={handleExport}
              disabled={!active}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <DownloadIcon className="h-4 w-4" />
              Export
            </button>
          </div>

          {/* Messages */}
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8">
            {messages.length === 0 ? (
              <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-200">
                  <BrainIcon className="h-7 w-7" />
                </div>

                <h2 className="mt-5 text-xl font-semibold text-slate-900">
                  Ask The Company Brain
                </h2>

                <p className="mt-1.5 text-sm text-slate-500">
                  Answers come from documents you have permission to access, with sources cited.
                </p>

                <div className="mt-6 flex w-full flex-col gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => send(suggestion)}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-5xl space-y-6">
                {messages.map((message) =>
                  message.role === "user" ? (
                    <UserMessage
                      key={message.id}
                      message={message}
                    />
                  ) : (
                    <AssistantMessage
                      key={message.id}
                      message={message}
                    />
                  )
                )}

                {loading && <TypingMessage />}

                <div ref={bottomRef} />
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="shrink-0 border-t border-slate-200 bg-white px-4 pb-3 pt-4 sm:px-8">
            <form
              onSubmit={handleSubmit}
              className="mx-auto flex max-w-3xl items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-2 pl-5 pr-2 transition focus-within:border-indigo-400 focus-within:bg-white focus-within:ring-4 focus-within:ring-indigo-100"
            >
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask anything about company policies, architecture, or documents..."
                aria-label="Ask a question"
                className="min-w-0 flex-1 bg-transparent py-1.5 text-sm text-slate-900 outline-none placeholder:text-slate-400"
              />

              <button
                type="button"
                aria-label="Attach a file"
                className="rounded-full p-2 text-slate-400 transition hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <PaperclipIcon className="h-4.5 w-4.5" />
              </button>

              <button
                type="submit"
                disabled={!input.trim() || loading}
                aria-label="Send question"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-white shadow-md shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 disabled:cursor-not-allowed disabled:bg-indigo-300 disabled:shadow-none"
              >
                <SendIcon className="h-4.5 w-4.5" />
              </button>
            </form>

            <p className="mt-2.5 text-center text-[11px] text-slate-400">
              The Company Brain uses secure Retrieval-Augmented Generation with strict RBAC permissioning.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}