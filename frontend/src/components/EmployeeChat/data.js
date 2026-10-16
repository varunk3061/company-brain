// Sample data. Replace with real data from your backend.

export const USER = {
  name: "Alex Turner",
  role: "Engineering Lead",
  initials: "AT",
  permission: "Level 3 (Engineering)",
};

export const SCOPES = [
  "All Corporate Repositories",
  "HR & Policies",
  "Engineering Docs",
  "Security & Compliance",
  "Finance",
];

export const SUGGESTIONS = [
  "What is the remote work expense policy?",
  "How does our API gateway authenticate requests?",
  "What is on the Q4 security audit checklist?",
];

export const INITIAL_CONVERSATIONS = [
  {
    id: "q1",
    num: 1,
    title: "Remote Work Expense Policy 2026",
    messages: [
      {
        id: "q1-u",
        role: "user",
        text: "What is the current corporate allowance for ergonomic home office setup under the 2026 remote work guidelines?",
      },
      {
        id: "q1-a",
        role: "assistant",
        paragraphs: [
          "Based on the verified corporate policy document [[HR-Policy-Remote-2026.pdf]] (Page 14), permanent full-time employees are entitled to a one-time ergonomic setup allowance of **$750 USD**.",
          "Eligible items include approved standing desks, ergonomic chairs, and ultra-wide external monitors verified through the internal procurement portal.",
        ],
        sources: [
          { file: "HR-Policy-Remote-2026.pdf", relevance: "96.4", page: 14 },
          { file: "Benefits-Overview-Q1.pdf", relevance: "89.1", page: 4 },
        ],
      },
    ],
  },
  {
    id: "q2",
    num: 2,
    title: "Microservice API Gateway Auth Flow",
    messages: [
      {
        id: "q2-u",
        role: "user",
        text: "How does authentication work across our microservice API gateway?",
      },
      {
        id: "q2-a",
        role: "assistant",
        paragraphs: [
          "According to [[Platform-Architecture-v3.pdf]] (Page 8), every request is authenticated at the gateway before it reaches a service. The gateway validates the **JWT access token**, checks the caller's role against the route policy, and forwards the verified identity to downstream services in a signed header.",
          "Service-to-service calls use short-lived **mTLS certificates** instead of user tokens.",
        ],
        sources: [
          { file: "Platform-Architecture-v3.pdf", relevance: "94.2", page: 8 },
          { file: "Gateway-Runbook.pdf", relevance: "87.6", page: 3 },
        ],
      },
    ],
  },
  {
    id: "q3",
    num: 3,
    title: "Q4 Enterprise Security Audit Checklist",
    messages: [
      {
        id: "q3-u",
        role: "user",
        text: "What is on the Q4 enterprise security audit checklist?",
      },
      {
        id: "q3-a",
        role: "assistant",
        paragraphs: [
          "Per [[Security-Audit-Q4-2026.pdf]] (Page 2), the Q4 audit covers four areas: **access reviews**, **dependency and vulnerability scans**, **secrets rotation**, and **incident response drills**.",
          "Each team lead submits evidence through the compliance portal before the audit window closes.",
        ],
        sources: [
          { file: "Security-Audit-Q4-2026.pdf", relevance: "95.8", page: 2 },
          { file: "Compliance-Handbook.pdf", relevance: "85.3", page: 11 },
        ],
      },
    ],
  },
];