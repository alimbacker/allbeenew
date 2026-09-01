"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import { Alert, Button, Field } from "@/components/ui";

export default function RegisterPage() {
  const { signUp } = useAuth();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  // Checked here as well as on the server so the guest never waits on a round
  // trip to learn they mistyped.
  const mismatch =
    form.confirm_password.length > 0 && form.password !== form.confirm_password;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError(null);
    try {
      await signUp(form);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account");
      setBusy(false);
    }
  };

  return (
    <main className="on-ink flex min-h-dvh flex-col bg-ink px-6 py-10 text-chalk">
      <Link href="/" className="mx-auto">
        <Logo />
      </Link>

      <div className="mx-auto mt-14 w-full max-w-sm">
        <h1 className="font-display text-3xl font-bold">Create your account</h1>
        <p className="mt-2 text-sm text-chalk-soft">
          One account covers every event you shoot.
        </p>

        <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
          {error && <Alert>{error}</Alert>}
          <Field
            label="Name"
            autoComplete="name"
            required
            value={form.name}
            onChange={set("name")}
          />
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={set("email")}
          />
          <Field
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            hint="At least 8 characters, mixing letters and numbers."
            value={form.password}
            onChange={set("password")}
          />
          <Field
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm_password}
            onChange={set("confirm_password")}
            error={mismatch ? "These don't match yet." : undefined}
          />
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={mismatch}>
            Create account
          </Button>
        </form>

        <p className="mt-6 text-sm text-chalk-soft">
          Already registered?{" "}
          <Link href="/login" className="text-honey hover:text-honey-bright">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
