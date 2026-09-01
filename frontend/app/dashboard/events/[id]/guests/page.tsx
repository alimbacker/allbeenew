"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { EventNav } from "@/components/event-nav";
import { Alert, EmptyState, Spinner } from "@/components/ui";
import { formatCount } from "@/lib/format";
import type { Event } from "@/types";

export default function GuestsPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getEvent(id)
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load"));
  }, [id]);

  if (error) return <Alert>{error}</Alert>;
  if (!event) {
    return (
      <div className="flex justify-center py-20 text-chalk-soft">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  const stats = event.stats;
  const searched = stats?.guests ?? 0;

  return (
    <div className="space-y-7">
      <h1 className="font-display text-3xl font-bold">Guests</h1>
      <EventNav eventId={event.id} />

      <div className="readout-strip sm:grid-cols-3">
        <div className="readout-cell">
          <span className="readout-value">{formatCount(searched)}</span>
          <span className="readout-label">Selfie searches</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats?.matches)}</span>
          <span className="readout-label">Photos matched</span>
        </div>
        <div className="readout-cell">
          <span className="readout-value">{formatCount(stats?.faces)}</span>
          <span className="readout-label">Faces indexed</span>
        </div>
      </div>

      {searched === 0 ? (
        <EmptyState
          title="No searches yet"
          body="Once guests scan the QR code and submit a selfie, their activity is counted here."
        />
      ) : (
        <p className="text-sm leading-relaxed text-chalk-soft">
          Guests use this event without accounts, so there is nothing to identify them by.
          We deliberately keep only the counts above and the selfie used for each search.
          Set a retention period under Settings to remove selfies automatically.
        </p>
      )}
    </div>
  );
}
