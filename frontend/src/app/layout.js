import Script from "next/script";
import "@fontsource-variable/inter";
import "./globals.css";
import { DEFAULT_THEME } from "@/config/theme";

export const metadata = {
  title: "The Company Brain",
  description: "Secure, permission-aware answers from your company's documents.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme={DEFAULT_THEME} className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full flex flex-col">
        <Script src="/theme-init.js" strategy="beforeInteractive" />
        {children}
      </body>
    </html>
  );
}
