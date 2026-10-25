import LoginCard from "@/components/LoginCard/LoginCard";

export const metadata = {
  title: "Sign in | The Company Brain",
};

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-linear-to-br from-canvas via-brand-tint/60 to-surface-3 px-4 py-10">
      <LoginCard />
    </main>
  );
}