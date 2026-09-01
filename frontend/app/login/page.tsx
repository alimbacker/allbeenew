"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import { Alert, Button, Field } from "@/components/ui";

export default function LoginPage() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
      setBusy(false);
    }
  };

  return (
    <main className="on-ink flex min-h-dvh flex-col bg-ink px-6 py-10 text-chalk">
      <Link href="/" className="mx-auto">
        <Logo />
      </Link>

      <div className="mx-auto mt-14 w-full max-w-sm">
        <h1 className="font-display text-3xl font-bold">Sign in</h1>
        <p className="mt-2 text-sm text-chalk-soft">Pick up where your last event left off.</p>

        <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
          {error && <Alert>{error}</Alert>}
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Field
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Button type="submit" size="lg" className="w-full" loading={busy}>
            Sign in
          </Button>
        </form>

        <p className="mt-6 text-sm text-chalk-soft">
          No account yet?{" "}
          <Link href="/register" className="text-honey hover:text-honey-bright">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}
