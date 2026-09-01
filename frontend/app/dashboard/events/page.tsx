"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCount, formatEventDate } from "@/lib/format";
import { Alert, EmptyState, LiveBadge, Spinner, StatusPill } from "@/components/ui";
import type { Event } from "@/types";

export default function EventsPage() {
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listEvents()
      .then(setEvents)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load events"));
  }, []);

  if (error) return <Alert>{error}</Alert>;
  if (!events) {
    return (
      <div className="flex justify-center py-20 text-chalk-soft">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-3xl font-bold">Events</h1>
        <Link
          href="/dashboard/events/create"
          className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
        >
          Create event
        </Link>
      </div>

      {events.length === 0 ? (
        <EmptyState
          title="Nothing here yet"
          body="An event holds your photos, its QR code and everything guests can see."
          action={
            <Link
              href="/dashboard/events/create"
              className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
            >
              Create your first event
            </Link>
          }
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {events.map((event) => (
            <li key={event.id}>
              <Link
                href={`/dashboard/events/${event.id}`}
                className="block h-full rounded-panel border border-line bg-ink-raised p-5 transition-colors hover:border-line-bright"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-display text-lg font-semibold text-chalk">{event.name}</h2>
                  {event.status === "LIVE" && event.public_access ? (
                    <LiveBadge />
                  ) : (
                    <StatusPill status={event.status} />
                  )}
                </div>
                <p className="mt-1 text-sm text-chalk-soft">
                  {[formatEventDate(event.event_date), event.location]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <p className="tnum mt-4 text-sm text-chalk-soft">
                  {formatCount(event.stats?.photos)} photos ·{" "}
                  {formatCount(event.stats?.guests)} guests ·{" "}
                  {formatCount(event.stats?.matches)} matches
                </p>
                <p className="tnum mt-3 text-micro text-honey">{event.event_code}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
