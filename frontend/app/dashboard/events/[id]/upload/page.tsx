"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { EventNav } from "@/components/event-nav";
import { PhotoUploader } from "@/components/photo-uploader";
import { Alert, Spinner } from "@/components/ui";
import { formatCount } from "@/lib/format";
import type { Event } from "@/types";

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api
      .getEvent(id)
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load"));

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <div>
        <h1 className="font-display text-3xl font-bold">Upload photos</h1>
        <p className="mt-1 text-sm text-chalk-soft">{event.name}</p>
      </div>

      <EventNav eventId={event.id} />

      <p className="text-sm text-chalk-soft">
        Photos appear in the guest gallery as soon as face processing finishes. Uploading
        the same file twice is safe — duplicates are detected and skipped.
      </p>

      <PhotoUploader eventId={event.id} onUploaded={load} />

      {event.stats && (
        <p className="tnum text-sm text-chalk-soft">
          {formatCount(event.stats.photos)} photos in this event ·{" "}
          {formatCount(event.stats.processed)} processed
          {event.stats.processing > 0 && (
            <> · {formatCount(event.stats.processing)} still processing</>
          )}
        </p>
      )}
    </div>
  );
}
