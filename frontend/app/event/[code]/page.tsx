"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatCount, formatEventDate } from "@/lib/format";
import { GuestShell } from "@/components/guest-shell";
import { Alert, LiveBadge, Spinner } from "@/components/ui";
import type { PublicEvent } from "@/types";

export default function GuestEventPage() {
  const { code } = useParams<{ code: string }>();
  const [event, setEvent] = useState<PublicEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .publicEvent(code)
      .then(setEvent)
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "We couldn't find an event with that code.",
        ),
      );
  }, [code]);

  if (error) {
    return (
      <GuestShell>
        <div className="mx-auto max-w-sm pt-16">
          <Alert>{error}</Alert>
          <p className="mt-4 text-sm text-bark-soft">
            Check the code on your table card, or ask the photographer for the link again.
          </p>
        </div>
      </GuestShell>
    );
  }

  if (!event) {
    return (
      <GuestShell>
        <div className="flex justify-center pt-24 text-bark-soft">
          <Spinner className="h-6 w-6" />
        </div>
      </GuestShell>
    );
  }

  return (
    <GuestShell>
      <div className="mx-auto flex max-w-sm flex-col items-center pt-10 text-center">
        {event.is_live && <LiveBadge label="Photos arriving now" />}

        <h1 className="mt-6 font-display text-4xl font-bold leading-tight text-bark">
          {event.name}
        </h1>
        <p className="mt-3 text-bark-soft">
          {[formatEventDate(event.event_date), event.location].filter(Boolean).join(" · ")}
        </p>
        {event.description && (
          <p className="mt-4 text-sm leading-relaxed text-bark-soft">{event.description}</p>
        )}

        <p className="tnum mt-8 font-display text-counter font-bold text-bark">
          {formatCount(event.photo_count)}
        </p>
        <p className="text-sm text-bark-soft">photos so far</p>

        <div className="mt-10 w-full space-y-3">
          <Link
            href={`/event/${code}/find`}
            className="block w-full rounded-control bg-honey px-6 py-4 text-center font-semibold text-ink hover:bg-honey-bright"
          >
            Find my photos
          </Link>
          <Link
            href={`/event/${code}/gallery`}
            className="block w-full rounded-control border border-bark/20 bg-paper-raised px-6 py-4 text-center text-bark hover:border-bark/40"
          >
            Browse all photos
          </Link>
        </div>

        <p className="mt-8 text-sm leading-relaxed text-bark-soft">
          No app and no account. Take one selfie and we&apos;ll pick out every photo
          you&apos;re in.
        </p>
      </div>
    </GuestShell>
  );
}
