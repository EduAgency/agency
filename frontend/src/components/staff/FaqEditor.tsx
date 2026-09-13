"use client";

/**
 * The FAQ block editor, inside the composer.
 *
 * Worth its own component because it is the highest-yield SEO feature the blog
 * has: the questions this audience asks are literal search queries, and
 * `FAQPage` markup is how those become rich results. Two good entries move a
 * page further than any amount of keyword work.
 *
 * Entries save one at a time rather than with the post. Nesting a writable,
 * ordered list inside the post payload makes a partial save ambiguous — and a
 * writer who adds a question and then navigates away should still have it.
 *
 * Answers go through the house-style scan server-side, so a claim in an answer
 * comes back as a field error rather than reaching the page.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { Alert, Button } from "@/components/ui";
import { type PostFaq, createFaq, deleteFaq, listFaqs, updateFaq } from "@/lib/blog-settings";

const inputStyle =
  "w-full rounded-lg border border-field-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-subtle";

export function FaqEditor({ postSlug }: { postSlug: string }) {
  const [faqs, setFaqs] = useState<PostFaq[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setFaqs(await listFaqs(postSlug));
  }, [postSlug]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await load();
      } catch {
        if (!cancelled) setError("Could not load the FAQ entries.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  async function add() {
    setBusy(true);
    setError("");
    try {
      await createFaq(postSlug, question.trim(), answer.trim(), (faqs.length + 1) * 10);
      setQuestion("");
      setAnswer("");
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? Object.entries(err.fieldErrors)
              .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
              .join(" · ") || err.message
          : "That did not save.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveOne(faq: PostFaq, patch: Partial<PostFaq>) {
    setBusy(true);
    setError("");
    try {
      await updateFaq(faq.id, patch);
      setEditing(null);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? Object.entries(err.fieldErrors)
              .map(([field, messages]) => `${field}: ${messages.join(" ")}`)
              .join(" · ") || err.message
          : "That did not save.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await deleteFaq(id);
      await load();
    } catch {
      setError("Could not remove that entry.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="faq-editor" className="rounded-xl border border-line bg-surface p-4">
      <h2 id="faq-editor" className="text-sm font-semibold text-ink">
        Short answers
      </h2>
      <p className="mt-1.5 text-xs leading-relaxed text-subtle">
        Two or three real questions, answered in a sentence or two. They appear on the article and
        as structured data, which is the cheapest way for this page to be found. Answers are checked
        against the house style.
      </p>

      {error ? (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      {faqs.length ? (
        <ol className="mt-4 space-y-3">
          {faqs.map((faq, index) => (
            <li key={faq.id} className="rounded-lg border border-line bg-sunken p-3">
              {editing === faq.id ? (
                <EditRow
                  faq={faq}
                  busy={busy}
                  onCancel={() => setEditing(null)}
                  onSave={(patch) => saveOne(faq, patch)}
                />
              ) : (
                <>
                  <p className="text-sm font-medium text-ink">{faq.question}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{faq.answer}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => setEditing(faq.id)}
                      className="font-semibold text-accent hover:underline"
                    >
                      Edit
                    </button>
                    {index > 0 ? (
                      <button
                        type="button"
                        onClick={() => saveOne(faq, { display_order: faq.display_order - 15 })}
                        className="text-muted hover:text-ink"
                      >
                        Move up
                      </button>
                    ) : null}
                    {index < faqs.length - 1 ? (
                      <button
                        type="button"
                        onClick={() => saveOne(faq, { display_order: faq.display_order + 15 })}
                        className="text-muted hover:text-ink"
                      >
                        Move down
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => remove(faq.id)}
                      className="text-danger hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ol>
      ) : null}

      <div className="mt-4 space-y-2.5 border-t border-line pt-4">
        <label htmlFor="new-faq-question" className="block text-xs font-semibold text-muted">
          Question
        </label>
        <input
          id="new-faq-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Can I apply with an HND?"
          maxLength={200}
          className={inputStyle}
        />
        <label htmlFor="new-faq-answer" className="block text-xs font-semibold text-muted">
          Answer
        </label>
        <textarea
          id="new-faq-answer"
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          rows={3}
          maxLength={1200}
          className={inputStyle}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={add}
          disabled={busy || !question.trim().endsWith("?") || answer.trim().length < 20}
        >
          {busy ? "Saving…" : "Add"}
        </Button>
        {question.trim() && !question.trim().endsWith("?") ? (
          <p className="text-xs text-warning">A question ends with a question mark.</p>
        ) : null}
      </div>
    </section>
  );
}

function EditRow({
  faq,
  busy,
  onCancel,
  onSave,
}: {
  faq: PostFaq;
  busy: boolean;
  onCancel: () => void;
  onSave: (patch: Partial<PostFaq>) => void;
}) {
  const [question, setQuestion] = useState(faq.question);
  const [answer, setAnswer] = useState(faq.answer);

  return (
    <div className="space-y-2.5">
      <label htmlFor={`faq-q-${faq.id}`} className="block text-xs font-semibold text-muted">
        Question
      </label>
      <input
        id={`faq-q-${faq.id}`}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        maxLength={200}
        className={inputStyle}
      />
      <label htmlFor={`faq-a-${faq.id}`} className="block text-xs font-semibold text-muted">
        Answer
      </label>
      <textarea
        id={`faq-a-${faq.id}`}
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        rows={3}
        maxLength={1200}
        className={inputStyle}
      />
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={() => onSave({ question: question.trim(), answer: answer.trim() })}
          disabled={busy}
        >
          Save
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
