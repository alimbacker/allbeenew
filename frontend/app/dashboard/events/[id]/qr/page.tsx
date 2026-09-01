"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { EventNav } from "@/components/event-nav";
import { Alert, Button, Spinner } from "@/components/ui";
import type { Event } from "@/types";

export default function QrPage() {
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

  return (
    <div className="space-y-7">
      <h1 className="font-display text-3xl font-bold">QR code</h1>
      <EventNav eventId={event.id} />

      {/* Printed on a table card, so the panel is laid out the way the card
          should be: name, instruction, code, nothing else. */}
      <div className="mx-auto max-w-md rounded-panel border border-line bg-paper p-8 text-center">
        <h2 className="font-display text-2xl font-bold text-bark">{event.name}</h2>
        <p className="mt-2 text-bark-soft">Scan to find your photos</p>

        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={api.qrUrl(event.id)}
          alt={`QR code linking to ${event.public_url}`}
          className="mx-auto mt-6 h-64 w-64"
        />

        <p className="tnum mt-4 font-display text-lg font-semibold text-bark">
          {event.event_code}
        </p>
        <p className="mt-2 text-sm text-bark-soft">
          Point your phone camera at the code. No app needed.
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <a
          href={api.qrUrl(event.id, true)}
          className="rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
        >
          Download PNG
        </a>
        <Button variant="secondary" onClick={() => window.print()}>
          Print
        </Button>
        <Button
          variant="secondary"
          onClick={() => navigator.clipboard.writeText(event.public_url)}
        >
          Copy guest link
        </Button>
      </div>
    </div>
  );
}
