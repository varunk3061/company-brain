// Shared icons come from the chat icon set; admin-only icons are defined here.
export {
  BrainIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  FileIcon,
  LogOutIcon,
  MenuIcon,
} from "../EmployeeChat/icons";

function Svg({ className = "h-5 w-5", strokeWidth = 1.8, children }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const GridIcon = (p) => (
  <Svg {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </Svg>
);

export const UsersIcon = (p) => (
  <Svg {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2A6.5 6.5 0 0 1 21.5 20" />
  </Svg>
);

export const FolderIcon = (p) => (
  <Svg {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </Svg>
);

export const ShieldIcon = (p) => (
  <Svg {...p}>
    <path d="M12 3 4.5 6v5.5c0 4.4 3 8.3 7.5 9.5 4.5-1.2 7.5-5.1 7.5-9.5V6z" />
  </Svg>
);

export const ShieldCheckIcon = (p) => (
  <Svg {...p}>
    <path d="M12 3 4.5 6v5.5c0 4.4 3 8.3 7.5 9.5 4.5-1.2 7.5-5.1 7.5-9.5V6z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const RefreshIcon = (p) => (
  <Svg {...p}>
    <path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4" />
    <path d="M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4" />
  </Svg>
);

export const TrendUpIcon = (p) => (
  <Svg strokeWidth={2} {...p}>
    <path d="m3 17 6-6 4 4 8-8M15 7h6v6" />
  </Svg>
);

export const CheckIcon = (p) => (
  <Svg strokeWidth={2.2} {...p}>
    <path d="m5 12 5 5 9-10" />
  </Svg>
);

export const ChatIcon = (p) => (
  <Svg {...p}>
    <path d="M21 12a8 8 0 0 1-8 8H4l1.8-3.6A8 8 0 1 1 21 12z" />
    <path d="M9 12h.01M12 12h.01M15 12h.01" strokeWidth="2.4" />
  </Svg>
);

export const FileCheckIcon = (p) => (
  <Svg {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="m9 14.5 2 2 4-4" />
  </Svg>
);

export const FilePlusIcon = (p) => (
  <Svg {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M12 11v6M9 14h6" />
  </Svg>
);

export const UserPlusIcon = (p) => (
  <Svg {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M19 8v6M16 11h6" />
  </Svg>
);

export const CloudUploadIcon = (p) => (
  <Svg {...p}>
    <path d="M7 18a4.5 4.5 0 0 1-.9-8.9A6 6 0 0 1 17.7 8 4.5 4.5 0 0 1 17 18" />
    <path d="m9 14 3-3 3 3M12 11v9" />
  </Svg>
);

export const FileUploadIcon = (p) => (
  <Svg {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M12 17v-6m-3 3 3-3 3 3" />
  </Svg>
);

export const AlertCircleIcon = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </Svg>
);

export const SearchIcon = (p) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Svg>
);
export const BuildingIcon = (p) => (
  <Svg {...p}>
    <path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16" />
    <path d="M14 10h5a1 1 0 0 1 1 1v10" />
    <path d="M8 8h2M8 12h2M8 16h2M3 21h18" />
  </Svg>
);
