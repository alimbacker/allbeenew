"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { GuestShell } from "@/components/guest-shell";
import { SelfieCapture } from "@/components/selfie-capture";
import { Alert, Button } from "@/components/ui";
import type { SelfieErrorCode } from "@/types";

/**
 * The guest-facing copy for each rejection. These say what to do next rather
 * than restating that something failed.
 */
const GUIDANCE: Record<SelfieErrorCode, { title: string; body: string }> = {
  NO_FACE: {
    title: "We couldn't find a face in that one",
    body: "Try again with your face filling more of the frame and good light on it.",
  },
  MULTIPLE_FACES: {
    title: "There's more than one person in that photo",
    body: "Take a selfie with just you in it, so we know which face to look for.",
  },
  INVALID_IMAGE: {
    title: "We couldn't read that file",
    body: "Use a JPG, PNG or WEBP photo taken with your phone camera.",
  },
  ENGINE_UNAVAILABLE: {
    title: "Photo matching is offline right now",
    body: "Let your photographer know. You can still browse all the photos.",
  },
};

export default function FindPhotosPage() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ title: string; body: string } | null>(null);

  const submit = async (blob: Blob, previewUrl: string) => {
    setPreview(previewUrl);
    setProblem(null);
    setBusy(true);
    try {
      const result = await api.search(code, blob);
      router.push(`/event/${code}/results/${result.search_id}`);
    } catch (err) {
      const fallback = {
        title: "That didn't work",
        body: err instanceof Error ? err.message : "Try again in a moment.",
      };
      const code_ = err instanceof ApiError ? (err.code as SelfieErrorCode | undefined) : undefined;
      setProblem(code_ && GUIDANCE[code_] ? GUIDANCE[code_] : fallback);
      setBusy(false);
      setPreview(null);
    }
  };

  return (
    <GuestShell>
      <div className="mx-auto max-w-sm pt-8">
        <Link href={`/event/${code}`} className="text-sm text-bark-soft hover:text-bark">
          Back
        </Link>

        <h1 className="mt-4 font-display text-3xl font-bold">Find your photos</h1>
        <p className="mt-2 text-bark-soft">
          One clear selfie is all we need. Face the camera, no sunglasses.
        </p>

        {problem && (
          <div className="mt-6">
            <Alert>
              <strong className="block">{problem.title}</strong>
              <span className="mt-1 block font-normal">{problem.body}</span>
            </Alert>
          </div>
        )}

        {preview && busy && (
          <div className="mt-6 overflow-hidden rounded-panel">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Your selfie" className="w-full" />
          </div>
        )}

        <div className="mt-6">
          <SelfieCapture onCapture={submit} busy={busy} />
        </div>

        <div className="mt-10 rounded-panel border border-bark/15 bg-paper-raised p-5">
          <h2 className="font-display font-semibold">What happens to your selfie</h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-bark-soft">
            <li>
              It is used to find photos of you at this event, and nowhere else. Your search
              never touches another photographer&apos;s photos.
            </li>
            <li>
              Your face is turned into a set of numbers so it can be compared against the
              photos. That happens on the photographer&apos;s own server — no outside
              service sees it.
            </li>
            <li>
              The photographer controls this event and can remove the photos and your
              selfie at any time.
            </li>
            <li>We don&apos;t ask for your name, email or phone number, and we don&apos;t store them.</li>
          </ul>
        </div>

        <p className="mt-6 text-center">
          <Link href={`/event/${code}/gallery`} className="text-sm text-bark-soft underline">
            Or just browse everything
          </Link>
        </p>
      </div>
    </GuestShell>
  );
}
