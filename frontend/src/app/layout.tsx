import type { Metadata } from "next";
import { JetBrains_Mono, Schibsted_Grotesk, Source_Sans_3 } from "next/font/google";
import { SessionProvider } from "@/lib/auth/SessionProvider";
import { AnnouncerProvider } from "@/components/ui/Announcer";
import { SITE_DESCRIPTION, SITE_URL } from "@/lib/seo";
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

/**
 * Site-wide metadata.
 *
 * `metadataBase` is what makes every relative `alternates.canonical` and every
 * Open Graph image URL that pages build through `@/lib/seo` resolve to an
 * absolute URL. Without it Next silently emits relative canonicals, which
 * crawlers treat as no canonical at all.
 *
 * The title template is a bare `%s` on purpose: pages build their own full
 * titles through `pageMetadata`, where the brand suffix sits alongside the
 * description and canonical rather than being bolted on here. `default` covers
 * the routes that set no title of their own.
 */
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Nasuru — tuition-free schools abroad, every requirement in writing",
    template: "%s",
  },
  description: SITE_DESCRIPTION,
  applicationName: "Nasuru",
  alternates: {
    canonical: "/",
    types: { "application/rss+xml": "/blog/rss.xml" },
  },
  formatDetection: { telephone: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${sourceSans.variable} ${schibsted.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-canvas font-sans text-ink antialiased">
        <SessionProvider>
          <AnnouncerProvider>{children}</AnnouncerProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
