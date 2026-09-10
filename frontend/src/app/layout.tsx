import type { Metadata } from "next";
import { SessionProvider } from "@/lib/auth/SessionProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nasuru — study abroad applications, tracked properly",
  description:
    "Document checklists, application tracking and review for Nigerian students applying to universities abroad.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-white text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
