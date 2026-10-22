// "use client";

// import { useState } from "react";
// import { CheckIcon, RefreshIcon } from "./icons";

// export default function SyncButton() {
//   const [state, setState] = useState("idle"); // idle | syncing | done

//   const handleSync = async () => {
//     if (state === "syncing") return;
//     setState("syncing");

//     // TODO: replace with your real call, e.g.
//     // await fetch("/api/admin/sync-index", { method: "POST" });
//     await new Promise((r) => setTimeout(r, 2000));

//     setState("done");
//     setTimeout(() => setState("idle"), 4000);
//   };

//   return (
//     <div className="flex flex-col items-start gap-2 sm:items-end">
//       <button
//         type="button"
//         onClick={handleSync}
//         disabled={state === "syncing"}
//         className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-70"
//       >
//         <RefreshIcon className={`h-4 w-4 ${state === "syncing" ? "animate-spin" : ""}`} />
//         {state === "syncing" ? "Syncing..." : "Sync RAG Vector Index"}
//       </button>
//       <p aria-live="polite" className="h-4 text-xs text-emerald-600">
//         {state === "done" && (
//           <span className="inline-flex items-center gap-1">
//             <CheckIcon className="h-3.5 w-3.5" />
//             Index synced just now
//           </span>
//         )}
//       </p>
//     </div>
//   );
// }