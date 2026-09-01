"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useLiveGallery } from "@/hooks/useLiveGallery";
import { GuestShell } from "@/components/guest-shell";
import { PhotoGrid } from "@/components/photo-grid";
import { Alert, Button, EmptyState, GridSkeleton } from "@/components/ui";
import { formatCount } from "@/lib/format";

export default function GuestGalleryPage() {
  const { code } = useParams<{ code: string }>();
  const { photos, total, hasMore, loading, error, connection, loadMore } = useLiveGallery(code);

  return (
    <GuestShell>
      <div className="mx-auto max-w-5xl pt-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href={`/event/${code}`} className="text-sm text-bark-soft hover:text-bark">
            Back
          </Link>
          <div className="flex items-center gap-3">
            {/* Honest about the connection: "Live" only when the stream is
                actually open, "Checking for new photos" when polling. */}
            {connection === "live" && (
              <span className="inline-flex items-center gap-2 text-sm text-go">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-go" aria-hidden />
                Live
              </span>
            )}
            {connection === "polling" && (
              <span className="text-sm text-bark-soft">Checking for new photos</span>
            )}
            <span className="tnum text-sm text-bark-soft">{formatCount(total)} photos</span>
          </div>
        </div>

        <h1 className="mt-4 font-display text-3xl font-bold">All photos</h1>
        <p className="mt-2 text-sm text-bark-soft">
          New photos appear here on their own. Tap any photo to see it full size or download it.
        </p>

        <div className="mt-6">
          {error && <Alert>{error}</Alert>}

          {loading ? (
            <GridSkeleton />
          ) : photos.length === 0 ? (
            <EmptyState
              surface="paper"
              title="No photos yet"
              body="The photographer hasn't uploaded anything so far. This page updates on its own — leave it open."
            />
          ) : (
            <>
              <PhotoGrid photos={photos} />
              {hasMore && (
                <div className="mt-6 flex justify-center">
                  <Button variant="secondary" surface="paper" onClick={() => void loadMore()}>
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="mt-10 text-center">
          <Link
            href={`/event/${code}/find`}
            className="inline-block rounded-control bg-honey px-6 py-3.5 font-semibold text-ink hover:bg-honey-bright"
          >
            Find just my photos
          </Link>
        </div>
      </div>
    </GuestShell>
  );
}
