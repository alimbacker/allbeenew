"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { GuestShell } from "@/components/guest-shell";
import { PhotoGrid } from "@/components/photo-grid";
import { Alert, GridSkeleton } from "@/components/ui";
import { formatCount } from "@/lib/format";
import type { SearchResult } from "@/types";

export default function ResultsPage() {
  const { code, searchId } = useParams<{ code: string; searchId: string }>();
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSearch(searchId)
      .then(setResult)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "We couldn't find those results."),
      );
  }, [searchId]);

  if (error) {
    return (
      <GuestShell>
        <div className="mx-auto max-w-sm pt-16">
          <Alert>{error}</Alert>
          <Link
            href={`/event/${code}/find`}
            className="mt-4 inline-block text-sm text-bark underline"
          >
            Search again
          </Link>
        </div>
      </GuestShell>
    );
  }

  if (!result) {
    return (
      <GuestShell>
        <div className="mx-auto max-w-5xl pt-10">
          <GridSkeleton />
        </div>
      </GuestShell>
    );
  }

  const scores = Object.fromEntries(
    result.matches.map((match) => [match.photo.id, match.similarity]),
  );

  return (
    <GuestShell>
      <div className="mx-auto max-w-5xl pt-8">
        <Link href={`/event/${code}`} className="text-sm text-bark-soft hover:text-bark">
          Back
        </Link>

        {result.match_count > 0 ? (
          <>
            <h1 className="mt-4 font-display text-3xl font-bold">Your photos</h1>
            <p className="mt-2 text-bark-soft">
              We found <span className="tnum font-semibold text-bark">
                {formatCount(result.match_count)}
              </span>{" "}
              {result.match_count === 1 ? "photo" : "photos"} with you in them.
            </p>

            <div className="mt-6">
              <PhotoGrid
                photos={result.matches.map((match) => match.photo)}
                scores={scores}
              />
            </div>

            <p className="mt-8 text-center text-sm text-bark-soft">
              Tap a photo to view, download or share it.
            </p>
          </>
        ) : (
          <div className="mx-auto max-w-sm pt-8 text-center">
            <h1 className="font-display text-3xl font-bold">No matches yet</h1>
            <p className="mt-3 text-bark-soft">
              We couldn&apos;t find you in the photos uploaded so far. If the event is still
              running, try again in a little while.
            </p>

            <div className="mt-8 rounded-panel border border-bark/15 bg-paper-raised p-5 text-left">
              <h2 className="font-display font-semibold">A better selfie usually helps</h2>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-bark-soft">
                <li>Find good light, and face towards it</li>
                <li>Look straight at the camera</li>
                <li>Take off sunglasses or anything covering your face</li>
                <li>Fill more of the frame with your face</li>
              </ul>
            </div>
          </div>
        )}

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link
            href={`/event/${code}/find`}
            className="rounded-control bg-honey px-6 py-3.5 font-semibold text-ink hover:bg-honey-bright"
          >
            Try another selfie
          </Link>
          <Link
            href={`/event/${code}/gallery`}
            className="rounded-control border border-bark/20 bg-paper-raised px-6 py-3.5 text-bark hover:border-bark/40"
          >
            Browse all photos
          </Link>
        </div>
      </div>
    </GuestShell>
  );
}
