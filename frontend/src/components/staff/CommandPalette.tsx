"use client";

/**
 * Ctrl/Cmd-K search across students and the review queue.
 *
 * Nothing in this product used to be findable except by navigation
 * (docs/enterprise-readiness.md §D4). Staff overwhelmingly arrive with an
 * identifier already in hand — an email, a surname, a payment reference — so
 * search is the fastest path to almost every task they do.
 *
 * Built as a real `combobox` with `aria-activedescendant` rather than a div
 * with a keydown handler: the arrow keys move a visual highlight while DOM
 * focus stays in the input, which is the only pattern that both sighted and
 * screen reader users can operate.
 */

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { listStudents, listReviewQueue } from "@/lib/staff";

interface Result {
  id: string;
  title: string;
  detail: string;
  href: string;
  group: string;
}

export interface PaletteController {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

export function useCommandPalette(): PaletteController {
  const [isOpen, setOpen] = useState(false);

  const open = useCallback(() => setOpen(true), []);
  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return { isOpen, open, close };
}

export function CommandPalette({ controller }: { controller: PaletteController }) {
  // Mounted only while open, so every open starts from clean state. The
  // alternative — one always-mounted component resetting itself in an effect
  // keyed on `isOpen` — is a second render every time and a lint error.
  if (!controller.isOpen) return null;
  return <PaletteDialog close={controller.close} />;
}

function PaletteDialog({ close }: { close: () => void }) {
  const router = useRouter();
  const listId = useId();

  const [term, setTerm] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [active, setActive] = useState(0);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  /** Focus goes back where it came from on close — a basic dialog courtesy. */
  useEffect(() => {
    const cameFrom = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => cameFrom?.focus();
  }, []);

  useEffect(() => {
    const trimmed = term.trim();
    // Nothing is set synchronously here: a short term simply has no results to
    // show, which is derived below rather than stored.
    if (trimmed.length < 2) return;

    let cancelled = false;
    // Debounced: staff type fast, and every keystroke is two API calls.
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const [students, queue] = await Promise.all([
          listStudents({ search: trimmed }).catch(() => null),
          listReviewQueue({ search: trimmed }).catch(() => null),
        ]);
        if (cancelled) return;

        const found: Result[] = [
          ...(students?.results ?? []).slice(0, 6).map((student) => ({
            id: `student-${student.id}`,
            title: student.user.full_name || student.user.email,
            detail: `${student.user.email} · ${student.stage_display}`,
            href: `/staff/students/${student.id}`,
            group: "Students",
          })),
          ...(queue?.results ?? []).slice(0, 6).map((item) => ({
            id: `item-${item.id}`,
            title: item.label,
            detail: item.student_email ?? item.category_name,
            href: `/staff/review?item=${item.id}`,
            group: "Review queue",
          })),
        ];
        setResults(found);
        setActive(0);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [term]);

  /**
   * A stale result list from a previous term must never be shown while the
   * term is too short to have searched for it.
   */
  const visible = term.trim().length < 2 ? [] : results;
  const highlighted = Math.min(active, Math.max(0, visible.length - 1));

  /**
   * Grouped for display, but each entry keeps its index in the flat list — the
   * arrow keys and `aria-activedescendant` both work off one sequence, so
   * grouping must not renumber anything.
   */
  const groups: { name: string; items: { result: Result; index: number }[] }[] = [];
  visible.forEach((result, index) => {
    const last = groups[groups.length - 1];
    if (last && last.name === result.group) last.items.push({ result, index });
    else groups.push({ name: result.group, items: [{ result, index }] });
  });

  function choose(result: Result) {
    close();
    router.push(result.href);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (visible.length ? (index + 1) % visible.length : 0));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (visible.length ? (index - 1 + visible.length) % visible.length : 0));
      return;
    }
    if (event.key === "Enter" && visible[highlighted]) {
      event.preventDefault();
      choose(visible[highlighted]);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]">
      {/* Clicking away closes. The button is the accessible equivalent, and is
          hidden from the reading order because Escape already does this. */}
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        onClick={close}
        className="absolute inset-0 bg-ink/30"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search students and the review queue"
        className="relative w-full max-w-xl overflow-hidden rounded-xl border border-line bg-surface shadow-2xl"
      >
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={visible.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            visible[highlighted] ? `${listId}-${visible[highlighted].id}` : undefined
          }
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search by name, email or document…"
          className="w-full border-b border-line bg-transparent px-4 py-3.5 text-sm text-ink placeholder:text-subtle"
        />

        <div aria-live="polite" className="sr-only">
          {searching
            ? "Searching"
            : results.length > 0
              ? `${results.length} results`
              : term.trim().length >= 2
                ? "No results"
                : ""}
        </div>

        {/**
         * `listbox` → `group` → `option`, with no `li` in between.
         *
         * The first version wrapped each option in an `<li>`, which broke the
         * required parent/child relationship: axe reported aria-required-children
         * and aria-required-parent as critical, and a screen reader would have
         * announced the options as list items rather than selectable results.
         * `group` is the one role ARIA permits between the two, and it carries
         * the section name properly instead of a loose heading.
         */}
        <div id={listId} role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto">
          {groups.map((group) => (
            <div key={group.name} role="group" aria-label={group.name}>
              <p
                aria-hidden="true"
                className="px-4 pt-3 pb-1 text-xs font-medium tracking-wide text-subtle uppercase"
              >
                {group.name}
              </p>
              {group.items.map(({ result, index }) => (
                /* eslint-disable-next-line jsx-a11y/click-events-have-key-events --
                   Keyboard interaction for this listbox lives on the combobox
                   input (arrows + Enter), per the ARIA APG pattern. Options in
                   an aria-activedescendant listbox must NOT be tab stops. */
                <div
                  key={result.id}
                  id={`${listId}-${result.id}`}
                  role="option"
                  tabIndex={-1}
                  aria-selected={index === highlighted}
                  onClick={() => choose(result)}
                  onMouseEnter={() => setActive(index)}
                  className={`cursor-pointer px-4 py-2.5 ${
                    index === highlighted ? "bg-sunken" : ""
                  }`}
                >
                  <p className="text-sm font-medium text-ink">{result.title}</p>
                  <p className="text-xs text-muted">{result.detail}</p>
                </div>
              ))}
            </div>
          ))}
        </div>

        {term.trim().length >= 2 && !searching && visible.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-muted">
            Nothing matches “{term.trim()}”.
          </p>
        )}

        <p className="border-t border-line px-4 py-2 text-xs text-subtle">
          <kbd className="font-mono">↑</kbd> <kbd className="font-mono">↓</kbd> to move ·{" "}
          <kbd className="font-mono">Enter</kbd> to open · <kbd className="font-mono">Esc</kbd> to
          close
        </p>
      </div>
    </div>
  );
}
