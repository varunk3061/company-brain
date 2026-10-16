import LoginCard from "@/components/LoginCard/LoginCard";

export const metadata = {
  title: "Sign in | The Company Brain",
};

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-indigo-50/60 to-slate-100 px-4 py-10">
      <LoginCard />
    </main>
  );
}