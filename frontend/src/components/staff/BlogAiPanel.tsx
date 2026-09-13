"use client";

/**
 * AI assist, inside the composer.
 *
 * The shape of this panel is the argument for how it should be used: it never
 * writes into the draft on its own. Every suggestion lands in a review area with
 * an explicit "Use this" button, because the moment generated text can appear in
 * the body without a person pressing something, the provenance field on the post
 * becomes a guess.
 *
 * Order matters too. Outline before draft, because an outline is cheap to read
 * and cheap to reject, and a writer who approves an outline they actually agree
 * with ends up editing far less prose. The "what we cannot claim" list that comes
 * back with the outline is the most useful thing on this panel — it is the model
 * telling the writer where it was tempted to invent something.
 */

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button } from "@/components/ui";
import { HouseStyleReview } from "@/components/staff/HouseStyleReview";
import {
  type AiInvolvement,
  type ArticleOutline,
  type HouseStyleReview as Review,
  type SeoSuggestion,
  type TitleSuggestion,
  aiAssist,
} from "@/lib/blog-admin";

type Busy = "outline" | "draft" | "seo" | "titles" | "rewrite" | null;

interface Props {
  title: string;
  body: string;
  enabled: boolean;
  model: string;
  /** Applies a suggestion to the draft, and records how AI was involved. */
  onApply: (patch: Record<string, unknown>, involvement: AiInvolvement) => void;
}

export function BlogAiPanel({ title, body, enabled, model, onApply }: Props) {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState("");

  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [mustCover, setMustCover] = useState("");
  const [instruction, setInstruction] = useState("");

  const [outline, setOutline] = useState<ArticleOutline | null>(null);
  const [draft, setDraft] = useState<{ body: string; review?: Review } | null>(null);
  const [seo, setSeo] = useState<SeoSuggestion | null>(null);
  const [titles, setTitles] = useState<TitleSuggestion | null>(null);

  async function run(task: Exclude<Busy, null>, payload: Record<string, unknown>) {
    setBusy(task);
    setError("");
    try {
      const response = await aiAssist(task, payload);
      if (response.outline) setOutline(response.outline);
      if (response.body) setDraft({ body: response.body, review: response.review });
      if (response.seo) setSeo(response.seo);
      if (response.titles) setTitles(response.titles);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 429
            ? "You have used this hour's assist allowance. It resets on the hour."
            : err.message
          : "The assist did not come back. Try again.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (!enabled) {
    return (
      <section aria-labelledby="ai-assist" className="rounded-xl border border-line bg-surface p-4">
        <h2 id="ai-assist" className="text-sm font-semibold text-ink">
          AI assist
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Not configured on this environment. Set{" "}
          <code className="font-mono">ANTHROPIC_API_KEY</code> on the API to turn it on — the
          composer works the same way without it.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="ai-assist" className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="ai-assist" className="text-sm font-semibold text-ink">
          AI assist
        </h2>
        <span className="font-mono text-xs text-subtle">{model}</span>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-subtle">
        Suggestions only. Nothing reaches the draft until you press a Use button, and the post
        records that AI was involved.
      </p>

      {error ? (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      {/* --- Outline ------------------------------------------------------ */}
      <div className="mt-4 space-y-2.5">
        <label htmlFor="ai-topic" className="block text-xs font-semibold text-muted">
          What should the article be about?
        </label>
        <input
          id="ai-topic"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          placeholder="Why your transcript is the document to start with"
          className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-subtle"
        />
        <details className="text-xs">
          <summary className="cursor-pointer text-muted">Add detail (optional)</summary>
          <div className="mt-2 space-y-2">
            <label htmlFor="ai-audience" className="block font-semibold text-muted">
              Who specifically is reading it?
            </label>
            <input
              id="ai-audience"
              value={audience}
              onChange={(event) => setAudience(event.target.value)}
              placeholder="Someone who finished an HND and thinks it disqualifies them"
              className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-subtle"
            />
            <label htmlFor="ai-must-cover" className="block font-semibold text-muted">
              It must cover
            </label>
            <textarea
              id="ai-must-cover"
              value={mustCover}
              onChange={(event) => setMustCover(event.target.value)}
              rows={2}
              className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink"
            />
          </div>
        </details>
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null || topic.trim().length < 5}
          onClick={() =>
            run("outline", {
              topic: topic.trim(),
              audience_note: audience.trim(),
              must_cover: mustCover.trim(),
            })
          }
        >
          {busy === "outline" ? "Planning…" : "Suggest an outline"}
        </Button>
      </div>

      {outline ? (
        <div className="mt-4 rounded-lg border border-line bg-sunken p-3">
          <h3 className="text-sm font-semibold text-ink">{outline.working_title}</h3>
          <p className="mt-1 text-xs text-muted">
            Answers: <span className="text-ink">{outline.reader_question}</span>
          </p>
          <ol className="mt-3 space-y-2">
            {outline.sections.map((section) => (
              <li key={section.heading} className="text-sm">
                <p className="font-medium text-ink">{section.heading}</p>
                <ul className="mt-0.5 ml-4 list-disc text-xs text-muted">
                  {section.covers.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>

          {outline.what_we_cannot_claim.length ? (
            <div className="mt-3 rounded-lg border border-warning-line bg-warning-bg px-3 py-2.5">
              <h4 className="text-xs font-semibold text-ink">
                Check or cut each of these before publishing
              </h4>
              <ul className="mt-1.5 ml-4 list-disc space-y-1 text-xs text-ink">
                {outline.what_we_cannot_claim.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                onApply({ title: outline.working_title, excerpt: outline.excerpt }, "outline")
              }
            >
              Use title and excerpt
            </Button>
            <Button
              type="button"
              disabled={busy !== null}
              onClick={() => run("draft", { outline })}
            >
              {busy === "draft" ? "Writing…" : "Write a draft from this"}
            </Button>
          </div>
        </div>
      ) : null}

      {draft ? (
        <div className="mt-4 rounded-lg border border-line bg-sunken p-3">
          <h3 className="text-sm font-semibold text-ink">Suggested draft</h3>
          {draft.review ? (
            <div className="mt-2">
              <HouseStyleReview
                review={draft.review}
                label="This draft passes the house-style scan."
              />
            </div>
          ) : null}
          <pre className="mt-2 max-h-64 overflow-auto rounded-lg border border-line bg-canvas p-3 text-xs leading-relaxed whitespace-pre-wrap text-ink">
            {draft.body}
          </pre>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <Button type="button" onClick={() => onApply({ body: draft.body }, "draft")}>
              Replace the body with this
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                onApply({ body: `${body ? `${body}\n\n` : ""}${draft.body}` }, "draft")
              }
            >
              Append to the body
            </Button>
          </div>
        </div>
      ) : null}

      {/* --- Working on an existing body ---------------------------------- */}
      <div className="mt-5 border-t border-line pt-4">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
          On what you have written
        </h3>
        <div className="mt-2.5 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={busy !== null || body.trim().length < 200}
            onClick={() => run("seo", { title, body })}
          >
            {busy === "seo" ? "Thinking…" : "Suggest search metadata"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={busy !== null || body.trim().length < 200}
            onClick={() => run("titles", { body, title })}
          >
            {busy === "titles" ? "Thinking…" : "Suggest titles"}
          </Button>
        </div>

        <div className="mt-3 space-y-2">
          <label htmlFor="ai-instruction" className="block text-xs font-semibold text-muted">
            Or tell it what to change
          </label>
          <input
            id="ai-instruction"
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="Cut the third section in half and make the opening answer the question"
            className="w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-subtle"
          />
          <Button
            type="button"
            variant="secondary"
            disabled={busy !== null || body.trim().length < 200 || instruction.trim().length < 5}
            onClick={() => run("rewrite", { body, instruction: instruction.trim() })}
          >
            {busy === "rewrite" ? "Revising…" : "Revise the draft"}
          </Button>
        </div>
      </div>

      {seo ? (
        <div className="mt-4 rounded-lg border border-line bg-sunken p-3 text-sm">
          <h3 className="font-semibold text-ink">Suggested metadata</h3>
          <dl className="mt-2 space-y-1.5 text-xs">
            <Row term="Search title" value={seo.meta_title} />
            <Row term="Meta description" value={seo.meta_description} />
            <Row term="Focus keyword" value={seo.focus_keyword} />
            <Row term="Excerpt" value={seo.excerpt} />
          </dl>
          {seo.internal_link_ideas.length ? (
            <div className="mt-2.5">
              <p className="text-xs font-semibold text-muted">Worth linking to, if it exists</p>
              <ul className="mt-1 ml-4 list-disc text-xs text-muted">
                {seo.internal_link_ideas.map((idea) => (
                  <li key={idea}>{idea}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="mt-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                onApply(
                  {
                    meta_title: seo.meta_title,
                    meta_description: seo.meta_description,
                    focus_keyword: seo.focus_keyword,
                    excerpt: seo.excerpt,
                  },
                  "edit",
                )
              }
            >
              Use this metadata
            </Button>
          </div>
        </div>
      ) : null}

      {titles ? (
        <div className="mt-4 rounded-lg border border-line bg-sunken p-3">
          <h3 className="text-sm font-semibold text-ink">Suggested titles</h3>
          <p className="mt-1 text-xs text-muted">{titles.why}</p>
          <ul className="mt-2.5 space-y-1.5">
            {titles.titles.map((option) => (
              <li key={option} className="flex items-start justify-between gap-3">
                <span className="text-sm text-ink">
                  {option}
                  {option === titles.recommended ? (
                    <span className="ml-2 rounded-full border border-accent px-2 py-0.5 text-xs text-accent">
                      recommended
                    </span>
                  ) : null}
                </span>
                <button
                  type="button"
                  onClick={() => onApply({ title: option }, "edit")}
                  className="shrink-0 text-xs font-semibold text-accent hover:underline"
                >
                  Use
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-muted">
        {term} <span className="font-normal text-subtle">({value.length} chars)</span>
      </dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
