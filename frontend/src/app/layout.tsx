import type { Metadata } from "next";
import { JetBrains_Mono, Schibsted_Grotesk, Source_Sans_3 } from "next/font/google";
import { SessionProvider } from "@/lib/auth/SessionProvider";
import { AnnouncerProvider } from "@/components/ui/Announcer";
import "./globals.css";

/**
 * Source Sans 3 for everything readable: it was drawn for interfaces and long
 * documents, holds up at 12px where most of this product's text lives, and
 * carries the Naira sign and the diacritics Nigerian names need.
 *
 * JetBrains Mono for the things people read back character by character —
 * referral codes, payment references — where a typeface that separates 0 from
 * O and 1 from l prevents a support ticket.
 */
const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-source-sans",
});

/**
 * Schibsted Grotesk for headings only.
 *
 * It has enough character to carry a marketing page and stays legible as a UI
 * heading at 15px, which a display face usually does not. Body text stays on
 * Source Sans 3 — mixing the two is the whole point of the pairing.
 */
const schibsted = Schibsted_Grotesk({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-schibsted",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Nasuru — study abroad applications, tracked properly",
  description:
    "Document checklists, application tracking and review for Nigerian students applying to universities abroad.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sourceSans.variable} ${schibsted.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-canvas font-sans text-ink antialiased">
        <SessionProvider>
          <AnnouncerProvider>{children}</AnnouncerProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
