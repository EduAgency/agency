import { ImageResponse } from "next/og";
import { getPricing, isPriceKnown } from "@/lib/pricing";

/**
 * The default share card.
 *
 * Every article and every page falls back to this when it has no hero image, and
 * most will — an article about proof-of-funds requirements has no honest
 * photograph. So it is typographic: the name, the one-line offer, and the fee.
 *
 * Deliberately not a per-article generated card. A dynamic OG image per post
 * means an edge function on every share-link crawl and a second place the
 * article's title has to be escaped correctly; one well-made card carries the
 * brand and costs nothing to serve.
 *
 * Colours are the light palette's literal values rather than CSS variables —
 * this renders outside the browser, where custom properties do not resolve.
 *
 * Every glyph here is basic Latin, deliberately. The renderer has no font of
 * its own for anything outside that range and silently drops what it cannot
 * fetch, so a naira sign or a tick mark comes out as a blank box. Hence "NGN
 * 5,000" rather than the symbol the rest of the site uses, and a drawn tick
 * rather than a character.
 */

export const alt = "Nasuru — international education agent";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  // The fee is fetched, not typed. `ascii` rather than `formatted` because this
  // renderer has no font for the naira sign and drops it silently — see the note
  // above. When the API is unreachable the card simply omits the price line
  // rather than showing a stale one.
  const pricing = await getPricing();
  const priceKnown = isPriceKnown(pricing);

  return new ImageResponse(
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: "#ffffff",
        padding: "72px 80px",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "#0f6d52",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <svg
            width="30"
            height="30"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#ffffff"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              fontSize: 40,
              fontWeight: 800,
              color: "#10231c",
              letterSpacing: "-0.02em",
            }}
          >
            Nasuru
          </div>
          <div style={{ fontSize: 20, color: "#4d6b60" }}>International education agent</div>
        </div>
      </div>

      <div
        style={{
          fontSize: 60,
          fontWeight: 800,
          lineHeight: 1.12,
          color: "#10231c",
          letterSpacing: "-0.03em",
          maxWidth: 940,
          display: "flex",
        }}
      >
        Tuition-free schools abroad, and every requirement in writing before you spend a naira.
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          fontSize: 24,
          color: "#4d6b60",
        }}
      >
        {priceKnown ? (
          <span style={{ color: "#0f6d52", fontWeight: 700 }}>{pricing.access_fee.ascii}</span>
        ) : null}
        <span>
          {priceKnown
            ? "covers everything until you land on campus"
            : "One fee covers everything until you land on campus"}
        </span>
      </div>
    </div>,
    size,
  );
}
