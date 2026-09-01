"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Alert, Button, Field, Textarea } from "@/components/ui";

export default function CreateEventPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", event_date: "", location: "", description: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createEvent({
        name: form.name,
        event_date: form.event_date || null,
        location: form.location || null,
        description: form.description || null,
      });
      router.push(`/dashboard/events/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the event");
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="font-display text-3xl font-bold">Create an event</h1>
      <p className="mt-2 text-sm text-chalk-soft">
        We generate the event code and guest link for you.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
        {error && <Alert>{error}</Alert>}
        <Field
          label="Event name"
          required
          placeholder="Mohamed Wedding"
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
        <Field
          label="Date"
          type="date"
          value={form.event_date}
          onChange={(event) => setForm({ ...form, event_date: event.target.value })}
        />
        <Field
          label="Location"
          placeholder="Nagore"
          value={form.location}
          onChange={(event) => setForm({ ...form, location: event.target.value })}
        />
        <Textarea
          label="Description"
          placeholder="Anything guests should know when they open the gallery."
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
        />
        <div className="flex gap-3">
          <Button type="submit" size="lg" loading={busy}>
            Create event
          </Button>
          <Button type="button" variant="ghost" size="lg" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
