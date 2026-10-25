import { api } from "./http";

// Ask a question. The server answers only from documents the signed-in user may see.
export const askCompanyBrain = (question) =>
  api("/api/rag/ask", { method: "POST", body: { question } });
