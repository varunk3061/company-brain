// Features that are planned but not built yet. The UI shows "Coming Soon" instead of fake data.
// Flip a flag to true only when the backend behind it exists.
export const FEATURES = {
  questionAnswering: true,
  scopeFilter: false,
  fileAttachments: false,
  chatExport: false,
  passwordReset: false,
  usageMetrics: false,
  securityStatus: false,
  // Legacy "Document Folder Path" form (server-side folder scan via DOCUMENTS_ROOT).
  // PDFs are now uploaded to storage instead; turn on only for local development.
  legacyFolderScan: false,
};
