"use client";

import { useEffect, useRef, useState } from "react";

import { getMyProfile } from "@/services/authService";
import { getDocuments } from "@/services/documentService";
import { getDepartments } from "@/services/orgService";
import { askCompanyBrain } from "@/services/ragService";
import { clearSession } from "@/services/http";
import { FEATURES } from "@/config/features";
import { displayName, titleCase } from "@/lib/format";
import ThemeSelect from "@/components/ui/ThemeSelect";
import { ClassificationBadge } from "@/components/ui/Badge";
import { ComingSoonNotice } from "@/components/ui/ComingSoon";
import { getConversations, getConversation } from "@/services/chatService";

import Sidebar from "./Sidebar";
import { AssistantMessage, TypingMessage, UserMessage } from "./Message";

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

const uid = () => Math.random().toString(36).slice(2, 10);

// Real answer from the RAG backend (permission-filtered, with citations).
async function askBrain(query, conversationId = null) {
  const data = await askCompanyBrain(query, conversationId);

  return {
    conversation_id: data.conversation_id,
    num: data.num,
    id: uid(),
    role: "assistant",
    paragraphs: (data.answer || "No answer was returned.")
      .split(/\n+/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean),
    sources: (data.sources || []).map((source) => ({
      file: source.source || "Unknown document",
      page: source.page,
      document_uuid: source.document_uuid,
    })),
  };
}

export default function ChatApp() {
  const [conversations, setConversations] = useState([]);

  const [activeId, setActiveId] = useState(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Control the sign-out confirmation modal
  const [showSignOutModal, setShowSignOutModal] = useState(false);

  // Logged-in employee profile from FastAPI.
  const [employee, setEmployee] = useState(null);
  const [profileError, setProfileError] = useState("");

  // Documents this user's role allows them to see (real RBAC output).
  const [documents, setDocuments] = useState(null);
  const [departments, setDepartments] = useState([]);

  const bottomRef = useRef(null);
  const menuRef = useRef(null);

  // Load the logged-in employee's profile.
  useEffect(() => {
    let cancelled = false;

    getDocuments()
      .then((result) => !cancelled && setDocuments(result))
      .catch(() => !cancelled && setDocuments([]));
    getDepartments()
      .then((result) => !cancelled && setDepartments(result))
      .catch(() => {});

    getConversations()
      .then((data) => {
        if (!cancelled && Array.isArray(data)) {
          const formatted = data.map((c) => ({
            ...c,
            id: c.id || c._id || c.conversation_id,
            messages: c.messages || c.message || [],
          }));
          setConversations(formatted);
        }
      })
      .catch(() => {});

    async function loadEmployeeProfile() {
      try {
        const profile = await getMyProfile();

        if (!cancelled) {
          setEmployee(profile);
          setProfileError("");
        }
      } catch (error) {
        if (!cancelled) {
          setProfileError(error.message || "Unable to load employee profile.");
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
  }, [conversations, loading, activeId]);

  // Close the profile menu when clicking outside it.
  useEffect(() => {
    const onClick = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
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
    conversations.find(
      (conversation) =>
        conversation.id === activeId || conversation._id === activeId,
    ) ?? null;

  const messages = active?.messages ?? [];

  const hasSources = messages.some((message) => message.sources?.length > 0);

  // Use the API profile, falling back to the existing mock data.
  const employeeName = displayName(employee?.name) || "Employee";

  const employeeRole = employee?.role_name || "Employee";

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
  const handleSelect = async (id) => {
    setActiveId(id);
    setSidebarOpen(false);

    // If messages are not loaded yet for this conversation, fetch them from backend
    try {
      const fullConv = await getConversation(id);
      const incomingMessages = fullConv?.messages || fullConv?.message;
      if (fullConv && incomingMessages) {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === id || c._id === id
              ? { ...c, messages: incomingMessages }
              : c,
          ),
        );
      }
    } catch (err) {
      console.error("Failed to load conversation message", err);
    }
  };

  // Send a message and display the response.
  const send = async (text) => {
    const query = text.trim();

    if (!query || loading || !FEATURES.questionAnswering) return;

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

      const title = query.length > 40 ? `${query.slice(0, 40)}...` : query;

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
                messages: [...conversation.messages, userMsg],
              }
            : conversation,
        ),
      );
    }

    setInput("");
    setLoading(true);

    try {
      const reply = await askBrain(query, activeId);

      const serverConvId = reply.conversation_id || convId;
      const serverNum = reply.num;

      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === convId
            ? {
                ...conversation,
                id: serverConvId,
                num: serverNum ?? conversation.num,
                messages: [...(conversation.messages || []), reply],
              }
            : conversation,
        ),
      );

      if (!activeId && serverConvId) {
        setActiveId(serverConvId);
      }
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
                messages: [...conversation.messages, errorReply],
              }
            : conversation,
        ),
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
        lines.push(`**${employeeName}:** ${message.text}`, "");
      } else {
        lines.push(
          `**The Company Brain:** ${message.paragraphs
            .join("\n\n")
            .replace(/\[\[|\]\]/g, "")}`,
          "",
        );

        message.sources?.forEach((source) =>
          lines.push(
            `- ${source.file || source.source} (page ${source.page ?? "unknown"})`,
          ),
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

  // Open the signout confirmation modal
  const handleSignOutClick = () => {
    setMenuOpen(false);
    setShowSignOutModal(true);
  };

  // Cancel signout and close modal
  const handleCancelSignOut = () => {
    setShowSignOutModal(false);
  };

  // Sign out after confirmation
  const handleConfirmSignOut = () => {
    clearSession();

    window.location.href = "/login";
  };

  //-------------------------------------------------------------------------------------------------------------------------------------------

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface text-ink">
      {/* Header */}
      <header className="relative z-40 flex h-18 shrink-0 items-center justify-between border-b border-line bg-surface px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label="Toggle sidebar"
            className="rounded-control p-2 text-ink-3 hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand lg:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>

          <div className="flex h-10 w-10 items-center justify-center rounded-control bg-brand text-on-brand shadow-card">
            <BrainIcon className="h-5 w-5" />
          </div>

          <span className="text-lg font-bold tracking-tight">
            The Company Brain
          </span>

          <span className="hidden rounded-full border border-brand/30 bg-brand-tint px-3 py-1 text-micro font-medium text-brand-text sm:inline">
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
            className="flex items-center gap-3 rounded-control px-2 py-1.5 transition hover:bg-surface-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand text-xs font-bold text-on-brand">
              {employeeInitials}
            </span>

            <span className="hidden text-left leading-tight sm:block">
              <span className="block text-sm font-semibold text-ink">
                {employeeName}
              </span>

              <span className="block text-xs text-ink-3">{employeeRole}</span>
            </span>

            <ChevronDownIcon className="h-4 w-4 text-ink-3" />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-72 rounded-control border border-line bg-surface p-1.5 shadow-card"
            >
              {profileError && (
                <p className="px-3 py-2 text-xs text-danger">{profileError}</p>
              )}

              {employee && (
                <div className="border-b border-line px-4 py-3">
                  <p className="text-sm font-semibold text-ink">
                    {employeeName}
                  </p>
                  <p className="text-xs text-ink-3">{employee.email}</p>
                  <p className="mt-1 text-xs text-ink-3">
                    {employee.department_name}
                  </p>
                </div>
              )}

              <ThemeSelect />
              <div className="my-1 border-t border-line" />

              <button
                role="menuitem"
                onClick={handleSignOutClick}
                className="flex w-full items-center gap-2 rounded-control px-3 py-2 text-left text-sm text-ink-2 transition hover:bg-danger-soft hover:text-danger"
              >
                <LogOutIcon className="h-4 w-4 text-ink-3" />
                Sign Out
              </button>
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
            className="fixed inset-0 z-20 bg-overlay lg:hidden"
          />
        )}

        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={handleSelect}
          onNew={handleNew}
          profile={employee}
          documentCount={documents ? documents.length : undefined}
          open={sidebarOpen}
        />

        {/* Main chat area */}
        <main className="flex min-w-0 flex-1 flex-col bg-surface-2">
          {/* Profile error, if the API call fails */}
          {profileError && (
            <p
              role="alert"
              className="border-b border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger"
            >
              Unable to load your profile: {profileError}
            </p>
          )}

          {/* Conversation title bar */}
          <div className="flex h-15 shrink-0 items-center justify-between border-b border-line bg-surface px-4 sm:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <h1 className="truncate text-base font-semibold text-ink">
                {active?.title ?? "New Knowledge Query"}
              </h1>

              {hasSources && (
                <span className="hidden shrink-0 items-center gap-1.5 rounded-full border border-success/30 bg-success-soft px-2.5 py-1 text-micro font-medium text-success sm:inline-flex">
                  <CheckCircleIcon className="h-3.5 w-3.5" />
                  Verified Sources
                </span>
              )}
            </div>

            {/* <button
              type="button"
              onClick={handleExport}
              disabled={!active || !FEATURES.chatExport}
              title={FEATURES.chatExport ? undefined : "Export is coming soon"}
              className="flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink-3 transition hover:bg-surface-3 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <DownloadIcon className="h-4 w-4" />
              Export
            </button> */}
          </div>

          {/* Messages */}
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8">
            {messages.length === 0 ? (
              <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-card bg-brand text-on-brand shadow-card">
                  <BrainIcon className="h-7 w-7" />
                </div>

                <h2 className="mt-5 text-xl font-semibold text-ink">
                  Ask The Company Brain
                </h2>

                <p className="mt-1.5 text-sm text-ink-3">
                  Answers will come only from documents you have permission to
                  access, with sources cited.
                </p>

                {!FEATURES.questionAnswering && (
                  <div className="mt-6 w-full">
                    <ComingSoonNotice title="Question answering isn't connected yet">
                      You can see what you are allowed to search below. Asking
                      questions will be enabled once the retrieval service is
                      ready.
                    </ComingSoonNotice>
                  </div>
                )}

                {/* Documents You Can Access — hidden from employee view
                <section className="mt-6 w-full rounded-card border border-line bg-surface text-left shadow-card">
                  <div className="flex items-center justify-between border-b border-line px-5 py-3">
                    <h3 className="text-sm font-semibold text-ink">
                      Documents You Can Access
                    </h3>
                    {documents && (
                      <span className="text-xs text-ink-3">
                        {documents.length}
                      </span>
                    )}
                  </div>
                  {documents === null && (
                    <p className="px-5 py-6 text-sm text-ink-3">
                      Loading documents…
                    </p>
                  )}
                  {documents?.length === 0 && (
                    <p className="px-5 py-6 text-sm text-ink-3">
                      No documents are available to your role yet.
                    </p>
                  )}
                  {documents?.length > 0 && (
                    <ul className="max-h-72 divide-y divide-line overflow-y-auto">
                      {documents.map((doc) => (
                        <li
                          key={doc.document_uuid}
                          className="flex items-center justify-between gap-3 px-5 py-3"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-ink">
                              {doc.document_name}
                            </p>
                            <p className="text-xs text-ink-3">
                              {doc.department_code
                                ? (departments.find(
                                    (d) => d.code === doc.department_code,
                                  )?.name ?? doc.department_code)
                                : "No owning department"}
                            </p>
                          </div>
                          <ClassificationBadge value={doc.classification} />
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                */}
              </div>
            ) : (
              <div className="mx-auto max-w-5xl space-y-6">
                {messages.map((message) =>
                  message.role === "user" ? (
                    <UserMessage
                      key={message.id}
                      message={message}
                      initials={employeeInitials}
                    />
                  ) : (
                    <AssistantMessage key={message.id} message={message} />
                  ),
                )}

                {loading && <TypingMessage />}

                <div ref={bottomRef} />
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="shrink-0 border-t border-line bg-surface px-4 pb-3 pt-4 sm:px-8">
            <form
              onSubmit={handleSubmit}
              className="mx-auto flex max-w-3xl items-center gap-2 rounded-full border border-line bg-surface-2 py-2 pl-5 pr-2 transition focus-within:border-brand focus-within:bg-surface focus-within:ring-4 focus-within:ring-brand/25"
            >
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={!FEATURES.questionAnswering}
                placeholder={
                  FEATURES.questionAnswering
                    ? "Ask anything about company policies, projects, or documents…"
                    : "Asking questions is coming soon"
                }
                aria-label="Ask a question"
                className="min-w-0 flex-1 bg-transparent py-1.5 text-sm text-ink outline-none placeholder:text-ink-3"
              />

              {/* <button
                type="button"
                disabled={!FEATURES.fileAttachments}
                title={FEATURES.fileAttachments ? undefined : "Attachments are coming soon"}
                aria-label="Attach a file"
                className="rounded-full p-2 text-ink-3 transition hover:text-ink-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              >
                <PaperclipIcon className="h-4.5 w-4.5" />
              </button> */}

              <button
                type="submit"
                disabled={
                  !input.trim() || loading || !FEATURES.questionAnswering
                }
                aria-label="Send question"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-brand text-on-brand shadow-card transition hover:bg-brand-hover focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/25 disabled:opacity-50 disabled:shadow-none"
              >
                <SendIcon className="h-4.5 w-4.5" />
              </button>
            </form>

            {/* <p className="mt-2.5 text-center text-micro text-ink-3">
              The Company Brain uses secure Retrieval-Augmented Generation with
              strict RBAC permissioning.
            </p> */}
          </div>
        </main>
      </div>

      {/* Confirmation Modal */}
      {showSignOutModal && (
        <div
          className="fixed inset-0 z-100 flex items-center justify-center bg-overlay px-4 backdrop-blur-sm"
          onClick={handleCancelSignOut}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="signout-modal-title"
            className="w-full max-w-md rounded-card border border-line bg-surface p-6 shadow-pop"
            onClick={(event) => event.stopPropagation()}
          >
            {/* Modal Icon */}
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft">
              <LogOutIcon className="h-7 w-7 text-danger" />
            </div>

            {/* Modal Heading */}
            <h2
              id="signout-modal-title"
              className="mt-4 text-center text-xl font-semibold text-ink"
            >
              Sign out?
            </h2>

            {/* Modal Description */}
            <p className="mt-2 text-center text-sm leading-6 text-ink-3">
              Are you sure you want to sign out of The Company Brain? You will
              need to log in again to access your account.
            </p>

            {/* Modal Actions */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelSignOut}
                className="rounded-control border border-line px-5 py-2.5 text-sm font-medium text-ink-2 transition hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-line-strong"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleConfirmSignOut}
                className="flex items-center gap-2 rounded-control bg-danger px-5 py-2.5 text-sm font-medium text-on-danger shadow-card transition hover:bg-danger-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-danger"
              >
                <LogOutIcon className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}