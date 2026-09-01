"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { EventNav } from "@/components/event-nav";
import { Alert, Button, Field, Spinner, Textarea } from "@/components/ui";
import type { Event } from "@/types";

export default function EventSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getEvent(id)
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load"));
  }, [id]);

  const patch = async (changes: Partial<Event>, message: string) => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      setEvent(await api.updateEvent(id, changes));
      setNote(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const destroy = async () => {
    if (!window.confirm(`Delete "${event?.name}" and every photo in it? This cannot be undone.`))
      return;
    try {
      await api.deleteEvent(id);
      router.push("/dashboard/events");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the event");
    }
  };

  if (error && !event) return <Alert>{error}</Alert>;
  if (!event) {
    return (
      <div className="flex justify-center py-20 text-chalk-soft">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <h1 className="font-display text-3xl font-bold">Settings</h1>
      <EventNav eventId={event.id} />

      {error && <Alert>{error}</Alert>}
      {note && <Alert tone="success">{note}</Alert>}

      <form
        className="max-w-lg space-y-5"
        onSubmit={(submitEvent) => {
          submitEvent.preventDefault();
          void patch(
            {
              name: event.name,
              event_date: event.event_date,
              location: event.location,
              description: event.description,
            },
            "Saved",
          );
        }}
      >
        <Field
          label="Event name"
          value={event.name}
          onChange={(input) => setEvent({ ...event, name: input.target.value })}
        />
        <Field
          label="Date"
          type="date"
          value={event.event_date ?? ""}
          onChange={(input) => setEvent({ ...event, event_date: input.target.value || null })}
        />
        <Field
          label="Location"
          value={event.location ?? ""}
          onChange={(input) => setEvent({ ...event, location: input.target.value || null })}
        />
        <Textarea
          label="Description"
          value={event.description ?? ""}
          onChange={(input) => setEvent({ ...event, description: input.target.value || null })}
        />
        <Button type="submit" loading={busy}>
          Save changes
        </Button>
      </form>

      <section className="max-w-lg space-y-4 rounded-panel border border-line bg-ink-raised p-5">
        <h2 className="font-display font-semibold">Guest access</h2>
        <p className="text-sm leading-relaxed text-chalk-soft">
          {event.status === "LIVE"
            ? "This event is live. Guests with the code can browse and search."
            : "This event is archived."}{" "}
          {event.public_access
            ? "The guest link is open."
            : "The guest link is closed — visitors see a message asking you to reopen it."}
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            onClick={() =>
              void patch(
                { status: event.status === "LIVE" ? "ARCHIVED" : "LIVE" },
                event.status === "LIVE" ? "Event archived" : "Event set live",
              )
            }
          >
            {event.status === "LIVE" ? "Archive event" : "Set live"}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              void patch(
                { public_access: !event.public_access },
                event.public_access ? "Guest link closed" : "Guest link reopened",
              )
            }
          >
            {event.public_access ? "Close guest link" : "Reopen guest link"}
          </Button>
        </div>
      </section>

      <section className="max-w-lg space-y-4 rounded-panel border border-line bg-ink-raised p-5">
        <h2 className="font-display font-semibold">Face processing</h2>
        <p className="text-sm leading-relaxed text-chalk-soft">
          Photos that failed to process can be retried — useful after fixing the face model
          setup on the server.
        </p>
        <Button
          variant="secondary"
          onClick={async () => {
            try {
              const result = await api.reprocess(id);
              setNote(result.message);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Could not requeue");
            }
          }}
        >
          Retry failed photos
        </Button>
      </section>

      <section className="max-w-lg space-y-4 rounded-panel border border-alert/30 bg-ink-raised p-5">
        <h2 className="font-display font-semibold text-alert">Delete this event</h2>
        <p className="text-sm leading-relaxed text-chalk-soft">
          Removes the event, its guest link, and every photo file on the server. There is no
          undo and no backup taken.
        </p>
        <Button variant="danger" onClick={destroy}>
          Delete event
        </Button>
      </section>
    </div>
  );
}
