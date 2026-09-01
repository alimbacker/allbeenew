"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatCount, formatEventDate } from "@/lib/format";
import { EventNav } from "@/components/event-nav";
import { Alert, Button, LiveBadge, Spinner, StatusPill } from "@/components/ui";
import type { Event } from "@/types";

const REFRESH_MS = 5000;

export default function EventOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEvent(await api.getEvent(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the event");
    }
  }, [id]);

  // Counters move while the photographer is uploading, so refresh them.
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  if (error) return <Alert>{error}</Alert>;
  if (!event) {
    return (
      <div className="flex justify-center py-20 text-chalk-soft">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  const stats = event.stats;
  const live = event.status === "LIVE" && event.public_access;

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold">{event.name}</h1>
          <p className="mt-1 text-sm text-chalk-soft">
            {[formatEventDate(event.event_date), event.location].filter(Boolean).join(" · ")}
          </p>
        </div>
        {live ? <LiveBadge /> : <StatusPill status={event.status} />}
      </div>

      <EventNav eventId={event.id} />

      <div className="readout-strip">
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats?.photos)}</span>
          <span className="readout-label">Photos</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats?.processed)}</span>
          <span className="readout-label">
            Processed
            {stats && stats.processing > 0 && (
              <span className="tnum ml-1.5 text-honey">
                {formatCount(stats.processing)} in progress
              </span>
            )}
          </span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats?.guests)}</span>
          <span className="readout-label">Guests</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value text-honey">{formatCount(stats?.matches)}</span>
          <span className="readout-label">Matches delivered</span>
        </div>
      </div>

      {stats && stats.failed > 0 && (
        <Alert>
          <span className="tnum">{stats.failed}</span> photo(s) failed face processing. Open
          Settings to retry them.
        </Alert>
      )}

      <div className="flex flex-wrap gap-3">
        <Link
          href={`/dashboard/events/${event.id}/upload`}
          className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
        >
          Upload photos
        </Link>
        <Link
          href={`/dashboard/events/${event.id}/gallery`}
          className="rounded-control border border-line px-5 py-2.5 text-sm hover:border-line-bright"
        >
          Event gallery
        </Link>
        <Link
          href={`/dashboard/events/${event.id}/qr`}
          className="rounded-control border border-line px-5 py-2.5 text-sm hover:border-line-bright"
        >
          QR code
        </Link>
        <a
          href={`/event/${event.event_code}`}
          target="_blank"
          rel="noreferrer"
          className="rounded-control border border-line px-5 py-2.5 text-sm hover:border-line-bright"
        >
          Open guest view
        </a>
      </div>

      <div className="rounded-panel border border-line bg-ink-raised p-5">
        <h2 className="font-display font-semibold">Guest link</h2>
        <p className="mt-1 text-sm text-chalk-soft">
          This is what the QR code opens. Anyone with it can browse the gallery and search
          for their photos.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <code className="tnum rounded-control bg-ink-sunken px-3 py-2 text-sm text-honey">
            {event.public_url}
          </code>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigator.clipboard.writeText(event.public_url)}
          >
            Copy link
          </Button>
        </div>
      </div>
    </div>
  );
}
