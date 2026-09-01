"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatCount, formatEventDate } from "@/lib/format";
import { Alert, Button, EmptyState, LiveBadge, Spinner, StatusPill } from "@/components/ui";
import type { Dashboard } from "@/types";

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load"));
  }, []);

  if (error) return <Alert>{error}</Alert>;
  if (!data) {
    return (
      <div className="flex justify-center py-20 text-chalk-soft">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  const { stats, recent_events: recent } = data;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-sm text-chalk-soft">Capture. Match. Deliver.</p>
        </div>
        <Link
          href="/dashboard/events/create"
          className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
        >
          Create event
        </Link>
      </div>

      {/* The readout strip: one instrument panel, not four floating cards. */}
      <div className="readout-strip">
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats.total_events)}</span>
          <span className="readout-label">Events</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats.total_photos)}</span>
          <span className="readout-label">Photos</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats.active_events)}</span>
          <span className="readout-label">Live now</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value text-honey">{formatCount(stats.photos_delivered)}</span>
          <span className="readout-label">Photos delivered</span>
        </div>
      </div>

      <section>
        <h2 className="font-display text-xl font-semibold">Recent events</h2>
        <div className="mt-4">
          {recent.length === 0 ? (
            <EmptyState
              title="No events yet"
              body="Create your first event, print the QR code, and start uploading."
              action={
                <Link
                  href="/dashboard/events/create"
                  className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
                >
                  Create event
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-line rounded-panel border border-line">
              {recent.map((event) => (
                <li key={event.id}>
                  <Link
                    href={`/dashboard/events/${event.id}`}
                    className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-4 hover:bg-ink-raised"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-display font-semibold text-chalk">
                        {event.name}
                      </p>
                      <p className="mt-0.5 truncate text-sm text-chalk-soft">
                        {[formatEventDate(event.event_date), event.location]
                          .filter(Boolean)
                          .join(" · ") || event.event_code}
                      </p>
                    </div>
                    <span className="tnum text-sm text-chalk-soft">
                      {formatCount(event.stats?.photos)} photos
                    </span>
                    <span className="tnum text-sm text-chalk-soft">
                      {formatCount(event.stats?.guests)} guests
                    </span>
                    {event.status === "LIVE" && event.public_access ? (
                      <LiveBadge />
                    ) : (
                      <StatusPill status={event.status} />
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
