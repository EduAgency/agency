"use client";

/**
 * Notification preferences, channel connection, and the in-app inbox.
 *
 * Three delivery channels: email, WhatsApp and Telegram. There is no SMS —
 * it is the most expensive per message, the least rich, the easiest to spoof,
 * and in Nigeria the one most associated with scams, which is the opposite of
 * what this product needs to signal.
 */

import { authFetch } from "@/lib/auth/client";

export type NotificationChannel = "email" | "whatsapp" | "telegram";

export interface ChannelState {
  channel: NotificationChannel;
  label: string;
  /** The agency has switched this channel on and finished configuring it. */
  available: boolean;
  /** We hold an address for this user here — a linked chat, an opted-in number. */
  connected: boolean;
  /** Email cannot be disconnected; it is the account's own address. */
  locked: boolean;
}

export interface CategoryState {
  category: string;
  label: string;
  description: string;
  /** Transactional. Email stays on whatever else the user does. */
  always_email: boolean;
  channels: Record<NotificationChannel, boolean>;
}

export interface TelegramState {
  available: boolean;
  bot_username: string;
  connected: boolean;
  username: string;
}

export interface WhatsAppState {
  available: boolean;
  number: string;
  opted_in: boolean;
}

export interface PreferenceCentre {
  channels: ChannelState[];
  categories: CategoryState[];
  quiet_hours: { start: string | null; end: string | null };
  telegram: TelegramState;
  whatsapp: WhatsAppState;
}

export function getPreferences() {
  return authFetch<PreferenceCentre>("/api/notifications/preferences/");
}

export function setPreference(
  category: string,
  channel: NotificationChannel,
  enabled: boolean,
) {
  return authFetch<{ detail: string }>("/api/notifications/preferences/", {
    method: "PATCH",
    body: { category, channel, enabled },
  });
}

export function setQuietHours(start: string | null, end: string | null) {
  return authFetch<{ detail: string }>("/api/notifications/quiet-hours/", {
    method: "PUT",
    body: { start, end },
  });
}

/** Returns a t.me deep link that expires; the bot links the chat on /start. */
export function connectTelegram() {
  return authFetch<{ url: string; bot_username: string; expires_in_seconds: number }>(
    "/api/notifications/telegram/",
    { method: "POST" },
  );
}

export function disconnectTelegram() {
  return authFetch<{ detail: string }>("/api/notifications/telegram/", { method: "DELETE" });
}

export function optInToWhatsApp() {
  return authFetch<{ detail: string }>("/api/notifications/whatsapp/", { method: "POST" });
}

export function optOutOfWhatsApp() {
  return authFetch<{ detail: string }>("/api/notifications/whatsapp/", { method: "DELETE" });
}

export interface InboxItem {
  id: string;
  category: string;
  category_display: string;
  subject: string;
  body: string;
  action_url: string;
  read_at: string | null;
  created_at: string;
}

export function getInbox() {
  return authFetch<{ unread: number; results: InboxItem[] }>("/api/notifications/");
}

export function markInboxRead() {
  return authFetch<{ detail: string }>("/api/notifications/", { method: "POST" });
}
