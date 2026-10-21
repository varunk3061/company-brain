import AdminShell from "@/components/admin/AdminShell";

export const metadata = {
  title: "Admin | The Company Brain",
};

export default function AdminLayout({ children }) {
  return <AdminShell>{children}</AdminShell>;
}