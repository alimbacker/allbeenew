"use client";

import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";
import { formatEventDate } from "@/lib/format";

export default function AccountSettingsPage() {
  const { user, signOut } = useAuth();
  if (!user) return null;

  return (
    <div className="max-w-lg space-y-7">
      <h1 className="font-display text-3xl font-bold">Settings</h1>

      <dl className="divide-y divide-line rounded-panel border border-line">
        <div className="flex justify-between gap-4 px-5 py-4">
          <dt className="text-sm text-chalk-soft">Name</dt>
          <dd className="text-sm text-chalk">{user.name}</dd>
        </div>
        <div className="flex justify-between gap-4 px-5 py-4">
          <dt className="text-sm text-chalk-soft">Email</dt>
          <dd className="text-sm text-chalk">{user.email}</dd>
        </div>
        <div className="flex justify-between gap-4 px-5 py-4">
          <dt className="text-sm text-chalk-soft">Member since</dt>
          <dd className="text-sm text-chalk">
            {formatEventDate(user.created_at.slice(0, 10))}
          </dd>
        </div>
      </dl>

      <p className="text-sm leading-relaxed text-chalk-soft">
        Storage location, upload limits and the face-match threshold are server settings.
        They live in <code className="text-honey">backend/.env</code> — see the README for
        what each one does.
      </p>

      <Button variant="secondary" onClick={signOut}>
        Sign out
      </Button>
    </div>
  );
}
