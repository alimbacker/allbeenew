"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { EventNav } from "@/components/event-nav";
import { PhotoGrid } from "@/components/photo-grid";
import { Alert, Button, EmptyState, GridSkeleton, StatusPill } from "@/components/ui";
import { formatCount } from "@/lib/format";
import type { Photo } from "@/types";

const PAGE_SIZE = 60;

export default function EventGalleryPage() {
  const { id } = useParams<{ id: string }>();
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (offset: number) => {
      try {
        const page = await api.listPhotos(id, PAGE_SIZE, offset);
        setPhotos((current) => (offset === 0 ? page.items : [...current, ...page.items]));
        setTotal(page.total);
        setHasMore(page.has_more);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load photos");
      } finally {
        setLoading(false);
      }
    },
    [id],
  );

  useEffect(() => {
    void load(0);
  }, [load]);

  const remove = async (photo: Photo) => {
    if (!window.confirm(`Delete ${photo.filename}? This cannot be undone.`)) return;
    try {
      await api.deletePhoto(photo.id);
      setPhotos((current) => current.filter((item) => item.id !== photo.id));
      setTotal((value) => Math.max(0, value - 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the photo");
    }
  };

  const unprocessed = photos.filter((photo) => photo.status !== "READY");

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-3xl font-bold">Gallery</h1>
        <p className="tnum text-sm text-chalk-soft">{formatCount(total)} photos</p>
      </div>

      <EventNav eventId={id} />

      {error && <Alert>{error}</Alert>}

      {unprocessed.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-ink-raised px-4 py-3 text-sm text-chalk-soft">
          <span className="tnum">{unprocessed.length}</span> photo(s) not yet visible to guests:
          {Array.from(new Set(unprocessed.map((photo) => photo.status))).map((status) => (
            <StatusPill key={status} status={status} />
          ))}
        </div>
      )}

      {loading ? (
        <GridSkeleton />
      ) : photos.length === 0 ? (
        <EmptyState
          title="No photos yet"
          body="Everything you upload shows up here, and in the guest gallery once it has been processed."
        />
      ) : (
        <>
          <PhotoGrid photos={photos} onDelete={remove} />
          {hasMore && (
            <div className="flex justify-center">
              <Button variant="secondary" onClick={() => void load(photos.length)}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
