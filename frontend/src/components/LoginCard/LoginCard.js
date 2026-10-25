"use client";

import { useState } from "react";
import { loginUser } from "@/services/authService";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginCard() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const next = {};
    if (!email.trim()) next.email = "Enter your email address.";
    else if (!EMAIL_RE.test(email)) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validate()) return;

    setLoading(true);
    setErrors({});

    try {
      const data = await loginUser({
        email: email.trim(),
        password,
      });

      // Check the actual token field returned by FastAPI.
      const token = data.access_token ?? data.token;

      if (!token) {
        setErrors({
          form: "Login succeeded, but no authentication token was returned. Check the FastAPI login response.",
        });
        return;
      }

      // Remember this device: persist the token.
      // Otherwise, keep it only for the current browser session.
      const storage = remember ? localStorage : sessionStorage;

      // Clear any old token from the other storage location.
      localStorage.removeItem("access_token");
      sessionStorage.removeItem("access_token");

      storage.setItem("access_token", token);

      // Admins land in the control center; everyone else in the chat.
      const permissions = data.user?.permissions ?? [];
      const isAdmin = ["users.manage", "documents.manage", "org.manage"].some(
        (permission) => permissions.includes(permission),
      );
      window.location.href = isAdmin ? "/admin" : "/dashboard";
    } catch (error) {
      setErrors({
        form: error.message || "Unable to sign in. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  };

  const inputBase =
    "block w-full rounded-control border bg-surface-2 py-3 pl-11 pr-4 text-sm text-ink placeholder:text-ink-3 outline-none transition focus:bg-surface focus:ring-4";
  const inputOk =
    "border-line focus:border-brand focus:ring-brand/25";
  const inputErr = "border-danger/30 focus:border-danger focus:ring-danger/25";

  return (
    <div className="w-full max-w-md rounded-card border border-line/80 bg-surface p-8 shadow-pop sm:p-10">
      {/* Brand */}
      <div className="flex flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-card bg-brand text-on-brand shadow-card">
          <svg
            viewBox="0 0 24 24"
            className="h-8 w-8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
            <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
            <path d="M12 5v13" />
          </svg>
        </div>
        <h1 className="mt-6 text-2xl font-bold tracking-tight text-ink">
          The Company Brain
        </h1>
        {/* <p className="mt-1.5 text-sm text-ink-3">
          Enterprise Knowledge Retrieval &amp; RAG System
        </p> */}
      </div>

      <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-5">
        {errors.form && (
          <div
            role="alert"
            className="rounded-control border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"
          >
            {errors.form}
          </div>
        )}

        {/* Email */}
        <div>
          <label
            htmlFor="email"
            className="mb-1.5 block text-sm font-medium text-ink-2"
          >
            Email
          </label>
          <div className="relative">
            <svg
              viewBox="0 0 24 24"
              className="pointer-events-none absolute left-4 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-ink-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <path d="m3 7 9 6 9-6" />
            </svg>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              aria-invalid={!!errors.email}
              className={`${inputBase} ${errors.email ? inputErr : inputOk}`}
            />
          </div>
          {errors.email && (
            <p className="mt-1.5 text-xs text-danger">{errors.email}</p>
          )}
        </div>

        {/* Password */}
        <div>
          <label
            htmlFor="password"
            className="mb-1.5 block text-sm font-medium text-ink-2"
          >
            Password
          </label>
          <div className="relative">
            <svg
              viewBox="0 0 24 24"
              className="pointer-events-none absolute left-4 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-ink-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <rect x="4" y="11" width="16" height="9" rx="2" />
              <path d="M8 11V8a4 4 0 0 1 8 0v3" />
            </svg>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              aria-invalid={!!errors.password}
              className={`${inputBase} pr-12 ${errors.password ? inputErr : inputOk}`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-control p-2 text-ink-3 transition hover:text-ink-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              {showPassword ? (
                <svg
                  viewBox="0 0 24 24"
                  className="h-4.5 w-4.5" 
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M3 3l18 18" />
                  <path d="M10.6 6.1A9.8 9.8 0 0 1 12 6c5 0 9 6 9 6a15 15 0 0 1-3.2 3.7M6.6 7.6A15 15 0 0 0 3 12s4 6 9 6a9 9 0 0 0 3.4-.7" />
                  <path d="M10 10a2.5 2.5 0 0 0 3.5 3.5" />
                </svg>
              ) : (
                <svg
                  viewBox="0 0 24 24"
                  className="h-4.5 w-4.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M3 12s4-6 9-6 9 6 9 6-4 6-9 6-9-6-9-6Z" />
                  <circle cx="12" cy="12" r="2.5" />
                </svg>
              )}
            </button>
          </div>
          {errors.password && (
            <p className="mt-1.5 text-xs text-danger">{errors.password}</p>
          )}
        </div>

        <p className="text-center text-xs text-ink-3">
          Forgot your password? Contact your system administrator.
        </p>

        {/* Remember + forgot */}
        {/* for future use */}
        {/* <div className="flex items-center justify-between"> */}
          {/* <label className="flex items-center gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-line-strong text-brand-text focus:ring-brand"
            />
            Remember this device
          </label> */}
          {/* <a
            href="/forgot-password"
            className="text-sm font-medium text-brand-text hover:text-brand-text focus:outline-none focus-visible:underline"
          >
            Forgot password?
          </a> */}
        {/* </div> */}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-control bg-brand px-4 py-3.5 text-sm font-semibold text-on-brand shadow-card transition hover:bg-brand-hover focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/25 disabled:opacity-70"
        >
          {loading ? (
            <>
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  stroke="currentColor"
                  strokeOpacity="0.3"
                  strokeWidth="3"
                />
                <path
                  d="M21 12a9 9 0 0 0-9-9"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              </svg>
              Signing in...
            </>
          ) : (
            <>
              Sign in 
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </>
          )}
        </button>
      </form>
    </div>
  );
}