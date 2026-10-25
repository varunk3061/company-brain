"use client";

import { useEffect, useState } from "react";
import StatCard from "./StatCard";
import ActivityTable from "./ActivityTable";
import { getDashboardData } from "@/services/dashboardService";
import { FEATURES } from "@/config/features";

// Numbers fall back to "0", text falls back to "-".
const num = (value) =>
  typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "0";

const text = (value) =>
  typeof value === "string" && value.trim() ? value : "-";

function timeAgo(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString();
}

function buildStats(stats = {}) {
  return [
    {
      id: "users",
      label: "Total Users",
      value: num(stats.total_users),
      icon: "users",
      iconTone: "indigo",
      note: { text: `+${num(stats.users_added_this_month)} this month`, tone: "good", icon: "trend" },
    },
    {
      id: "docs",
      label: "Indexed Documents",
      value: num(stats.indexed_documents),
      icon: "file",
      iconTone: "emerald",
      note: { text: `${num(stats.documents_classified)} classified with access rules`, tone: "good", icon: "check" },
    },
    {
      id: "queries",
      label: "Daily RAG Queries",
      value: num(stats.daily_rag_queries),
      comingSoon: !FEATURES.usageMetrics,
      icon: "chat",
      iconTone: "indigo",
      note: {
        text: FEATURES.usageMetrics
          ? `Avg latency: ${num(stats.avg_latency_ms)}ms`
          : "Not tracked yet",
        tone: "muted",
        icon: "none",
      },
    },
    {
      id: "security",
      label: "System Security Status",
      value: text(stats.security_status),
      comingSoon: !FEATURES.securityStatus,
      icon: "shield",
      iconTone: "emerald",
      note: { text: `${num(stats.blocked_users)} blocked accounts`, tone: "muted", icon: "none" },
    },
  ];
}

export default function DashboardOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getDashboardData()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load dashboard.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const stats = buildStats(data?.stats);

  const rows = (Array.isArray(data?.activity) ? data.activity : []).map((row, index) => ({
    id: row.id ?? index,
    type: row.type,
    event: text(row.event),
    actor: text(row.actor),
    dept: text(row.dept),
    status: text(row.status),
    time: timeAgo(row.timestamp),
  }));

  return (
    <>
      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((s) => (
          <StatCard key={s.id} stat={s} />
        ))}
      </div>

      <ActivityTable
        rows={rows}
        emptyMessage={loading ? "Loading activity…" : "No recent activity yet."}
      />
    </>
  );
}
