"use client";

/**
 * The notification preference centre.
 *
 * Design decisions worth naming, because each one is a way this screen usually
 * goes wrong (docs/enterprise-readiness.md §C, "Notification prefs"):
 *
 *   1. **A channel you cannot use is never offered as a toggle.** Telegram and
 *      WhatsApp appear only once the agency has configured them, and their
 *      per-category switches stay disabled until this user has actually
 *      connected. A toggle that silently does nothing is worse than no toggle:
 *      the student opts in, stops watching email, and misses a rejection.
 *   2. **Transactional email is shown as locked, not hidden.** Security and
 *      payment mail cannot be switched off, and saying so plainly is more
 *      honest than quietly omitting the row.
 *   3. **Every change saves immediately and says so**, with the previous state
 *      restored if the server refuses. A Save button on a matrix of toggles is
 *      a way to lose changes.
 *   4. **The whole grid is one table with real headers**, so a screen reader
 *      user hears "Documents, WhatsApp, checked" rather than "checkbox, checked".
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/auth/SessionProvider";
import { useAnnouncer } from "@/components/ui/Announcer";
import { Alert, BackLink, Button, LoadingRegion, ScrollableX, Skeleton } from "@/components/ui";
import {
  connectTelegram,
  disconnectTelegram,
  getPreferences,
  optInToWhatsApp,
  optOutOfWhatsApp,
  setPreference,
  setQuietHours,
  type CategoryState,
  type NotificationChannel,
  type PreferenceCentre,
} from "@/lib/notifications";

const CHANNEL_HELP: Record<NotificationChannel, string> = {
  email: "Always available. Goes to the address on your account.",
  whatsapp: "Needs your number and your permission before we can message you.",
  telegram: "Connect once, and updates arrive in a chat with our bot.",
};

export default function NotificationSettingsPage() {
  const { loading, session, handleApiError } = useSession();
  const { announce, toast } = useAnnouncer();

  const [data, setData] = useState<PreferenceCentre | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);
  /** Ask for a fresh copy. Used by the child cards after they change something. */
  const reload = useCallback(async () => {
    setReloadKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (loading || !session) return;
    let cancelled = false;

    void (async () => {
      try {
        const fresh = await getPreferences();
        if (!cancelled) {
          setData(fresh);
          setError("");
        }
      } catch (err) {
        if (cancelled) return;
        if (!handleApiError(err)) setError("We couldn't load your notification settings.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loading, session, handleApiError, reloadKey]);

  async function toggle(category: CategoryState, channel: NotificationChannel) {
    if (!data) return;
    const next = !category.channels[channel];
    const key = `${category.category}:${channel}`;
    setSaving(key);

    // Optimistic, then reverted if the server disagrees — a toggle that lags
    // behind the finger feels broken even when it is working.
    setData({
      ...data,
      categories: data.categories.map((row) =>
        row.category === category.category
          ? { ...row, channels: { ...row.channels, [channel]: next } }
          : row,
      ),
    });

    try {
      await setPreference(category.category, channel, next);
      announce(`${category.label} on ${channel}: ${next ? "on" : "off"}`);
    } catch (err) {
      await reload();
      toast(
        err instanceof ApiError ? err.message : "That change didn't save. Try again.",
        "error",
      );
    } finally {
      setSaving(null);
    }
  }

  if (loading || !data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12">
        <LoadingRegion label="Loading your notification settings">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-6 h-64 w-full" />
        </LoadingRegion>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <BackLink href="/dashboard">Back to dashboard</BackLink>

      <header className="mt-6">
        <h1 className="text-2xl font-semibold text-ink">How we reach you</h1>
        <p className="mt-1 text-sm text-muted">
          Choose what you hear about and where. Changes save as you make them.
        </p>
      </header>

      {error && (
        <div className="mt-6">
          <Alert>{error}</Alert>
        </div>
      )}

      <ConnectionCards data={data} onChanged={reload} />

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-ink">What you hear about</h2>
        <p className="mt-1 text-sm text-muted">
          A channel you haven&apos;t connected stays greyed out until you do.
        </p>

        <ScrollableX label="Notification preferences" className="mt-4 rounded-xl border border-line">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">
              Notification preferences by category and channel. Each checkbox saves immediately.
            </caption>
            <thead>
              <tr className="border-b border-line bg-sunken">
                <th scope="col" className="px-4 py-2.5 font-medium text-ink">
                  Notify me about
                </th>
                {data.channels.map((channel) => (
                  <th
                    key={channel.channel}
                    scope="col"
                    className="px-4 py-2.5 text-center font-medium text-ink"
                  >
                    {channel.label}
                    {!channel.available && (
                      <span className="block text-xs font-normal text-subtle">unavailable</span>
                    )}
                    {channel.available && !channel.connected && !channel.locked && (
                      <span className="block text-xs font-normal text-subtle">not connected</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.categories.map((category) => (
                <tr key={category.category} className="border-b border-line last:border-0">
                  <th scope="row" className="px-4 py-3 font-normal">
                    <span className="font-medium text-ink">{category.label}</span>
                    <span className="mt-0.5 block text-xs text-muted">{category.description}</span>
                  </th>

                  {data.channels.map((channel) => {
                    const locked = category.always_email && channel.channel === "email";
                    const usable =
                      channel.available && (channel.connected || channel.locked) && !locked;
                    const id = `pref-${category.category}-${channel.channel}`;
                    const key = `${category.category}:${channel.channel}`;

                    return (
                      <td key={channel.channel} className="px-4 py-3 text-center">
                        <input
                          id={id}
                          type="checkbox"
                          checked={locked ? true : category.channels[channel.channel]}
                          disabled={!usable || saving === key}
                          onChange={() => toggle(category, channel.channel)}
                          className="h-4 w-4 rounded border-field-line disabled:opacity-40"
                        />
                        <label htmlFor={id} className="sr-only">
                          {category.label} by {channel.label}
                          {locked && " (always on — this is how you keep control of your account)"}
                          {!channel.available && " (unavailable)"}
                          {channel.available && !channel.connected && !channel.locked &&
                            ` (connect ${channel.label} first)`}
                        </label>
                        {locked && (
                          <span aria-hidden="true" className="mt-1 block text-xs text-subtle">
                            always
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableX>

        <p className="mt-3 text-xs text-subtle">
          Security and payment emails are always on. They are how you keep control of your account,
          so they are not something we let you switch off.
        </p>
      </section>

      <QuietHours data={data} onChanged={reload} />
    </div>
  );
}

function ConnectionCards({
  data,
  onChanged,
}: {
  data: PreferenceCentre;
  onChanged: () => Promise<void>;
}) {
  return (
    <section className="mt-8 space-y-3">
      <h2 className="text-lg font-semibold text-ink">Your channels</h2>

      <div className="rounded-xl border border-line p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-medium text-ink">Email</h3>
            <p className="mt-0.5 text-sm text-muted">{CHANNEL_HELP.email}</p>
          </div>
          <span className="text-xs font-medium text-success">Connected</span>
        </div>
      </div>

      {data.whatsapp.available && <WhatsAppCard data={data} onChanged={onChanged} />}
      {data.telegram.available && <TelegramCard data={data} onChanged={onChanged} />}
    </section>
  );
}

function WhatsAppCard({
  data,
  onChanged,
}: {
  data: PreferenceCentre;
  onChanged: () => Promise<void>;
}) {
  const { toast } = useAnnouncer();
  const [busy, setBusy] = useState(false);

  async function act() {
    setBusy(true);
    try {
      const response = data.whatsapp.opted_in ? await optOutOfWhatsApp() : await optInToWhatsApp();
      toast(response.detail, "success");
      await onChanged();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "That didn't work. Try again.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-ink">WhatsApp</h3>
          <p className="mt-0.5 text-sm text-muted">
            {data.whatsapp.number
              ? `Messages would go to ${data.whatsapp.number}.`
              : "Add a WhatsApp number to your profile first."}
          </p>
          {/* Consent is a recorded act, not an inferred one — WhatsApp's own
              policy requires the business to be able to evidence it. */}
          {!data.whatsapp.opted_in && data.whatsapp.number && (
            <p className="mt-1 text-xs text-subtle">
              We&apos;ll only message you about your application, never marketing.
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {data.whatsapp.opted_in && (
            <span className="text-xs font-medium text-success">Connected</span>
          )}
          <Button
            variant="secondary"
            onClick={act}
            disabled={busy || !data.whatsapp.number}
          >
            {busy ? "Saving…" : data.whatsapp.opted_in ? "Turn off" : "Turn on"}
            <span className="sr-only"> WhatsApp messages</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

function TelegramCard({
  data,
  onChanged,
}: {
  data: PreferenceCentre;
  onChanged: () => Promise<void>;
}) {
  const { toast } = useAnnouncer();
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState("");

  async function connect() {
    setBusy(true);
    try {
      const response = await connectTelegram();
      setLink(response.url);
      // Opened rather than navigated to: losing this page mid-flow would lose
      // the explanation of what is about to happen.
      window.open(response.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Couldn't start the connection.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await disconnectTelegram();
      setLink("");
      toast("Telegram is disconnected.", "success");
      await onChanged();
    } catch {
      toast("That didn't work. Try again.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-ink">Telegram</h3>
          <p className="mt-0.5 text-sm text-muted">
            {data.telegram.connected
              ? `Connected${data.telegram.username ? ` as @${data.telegram.username}` : ""}.`
              : CHANNEL_HELP.telegram}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {data.telegram.connected && (
            <span className="text-xs font-medium text-success">Connected</span>
          )}
          <Button variant="secondary" onClick={data.telegram.connected ? disconnect : connect} disabled={busy}>
            {busy ? "Working…" : data.telegram.connected ? "Disconnect" : "Connect"}
            <span className="sr-only"> Telegram</span>
          </Button>
        </div>
      </div>

      {/* The new tab may be blocked, and on mobile the app switch can drop the
          link entirely — so it is also shown here, and the page says what to
          expect rather than leaving the user staring at a bot. */}
      {link && !data.telegram.connected && (
        <div className="mt-3 rounded-lg bg-sunken p-3" aria-live="polite">
          <p className="text-sm text-muted">
            Telegram should have opened. Press <strong>Start</strong> in the chat with{" "}
            <span className="font-mono">@{data.telegram.bot_username}</span>, then come back and
            refresh this page.
          </p>
          <p className="mt-2 text-sm">
            <a href={link} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
              Open the chat again
            </a>{" "}
            · the link expires in 15 minutes.
          </p>
          <button
            type="button"
            onClick={() => void onChanged()}
            className="mt-2 text-sm text-muted underline underline-offset-2 hover:text-ink"
          >
            I&apos;ve done it — check again
          </button>
        </div>
      )}
    </div>
  );
}

function QuietHours({ data, onChanged }: { data: PreferenceCentre; onChanged: () => Promise<void> }) {
  const { toast } = useAnnouncer();
  const [start, setStart] = useState(data.quiet_hours.start?.slice(0, 5) ?? "");
  const [end, setEnd] = useState(data.quiet_hours.end?.slice(0, 5) ?? "");
  const [busy, setBusy] = useState(false);

  async function save(nextStart: string, nextEnd: string) {
    setBusy(true);
    try {
      await setQuietHours(nextStart || null, nextEnd || null);
      toast(nextStart && nextEnd ? "Quiet hours saved." : "Quiet hours turned off.", "success");
      await onChanged();
    } catch {
      toast("That didn't save. Try again.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-10 rounded-xl border border-line p-5">
      <h2 className="text-lg font-semibold text-ink">Quiet hours</h2>
      <p className="mt-1 text-sm text-muted">
        Outside these hours we hold everything non-urgent until morning. Payment receipts and
        security alerts still come through — those are time-sensitive.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-4">
        <div>
          <label htmlFor="quiet-start" className="block text-sm font-medium text-ink">
            From
          </label>
          <input
            id="quiet-start"
            type="time"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            className="mt-1 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink"
          />
        </div>
        <div>
          <label htmlFor="quiet-end" className="block text-sm font-medium text-ink">
            Until
          </label>
          <input
            id="quiet-end"
            type="time"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            className="mt-1 rounded-lg border border-field-line bg-surface px-3 py-2 text-sm text-ink"
          />
        </div>

        <Button onClick={() => save(start, end)} disabled={busy || !start || !end}>
          {busy ? "Saving…" : "Save"}
        </Button>

        {(data.quiet_hours.start || data.quiet_hours.end) && (
          <button
            type="button"
            onClick={() => {
              setStart("");
              setEnd("");
              void save("", "");
            }}
            disabled={busy}
            className="pb-2 text-sm text-muted underline underline-offset-2 hover:text-ink"
          >
            Turn off
          </button>
        )}
      </div>

      <p className="mt-3 text-xs text-subtle">Times are West Africa Time.</p>
    </section>
  );
}
