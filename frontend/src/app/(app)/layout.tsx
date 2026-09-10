import { AppShell } from "@/components/AppShell";

/**
 * One frame for every signed-in route, replacing the header each page used to
 * build for itself (§B1).
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
