"use client";

/**
 * Masonry photo grid and its fullscreen viewer.
 *
 * The grid only ever requests thumbnails. The original is fetched when a photo
 * is actually opened, which is what keeps a 5,000-photo gallery usable on
 * venue wifi.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/format";
import { mediaUrl } from "@/lib/api";
import { Button } from "@/components/ui";
import type { Photo } from "@/types";

interface GridProps {
  photos: Photo[];
  scores?: Record<string, number>;
  onDelete?: (photo: Photo) => void;
  emptyLabel?: string;
}

export function PhotoGrid({ photos, scores, onDelete, emptyLabel }: GridProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!photos.length && emptyLabel) {
    return <p className="py-12 text-center text-sm text-chalk-soft">{emptyLabel}</p>;
  }

  return (
    <>
      <div className="masonry">
        {photos.map((photo, index) => (
          <figure key={photo.id} className="group relative animate-rise-in">
            <button
              type="button"
              onClick={() => setOpenIndex(index)}
              className="block w-full overflow-hidden rounded-control bg-ink-raised"
              aria-label={`Open ${photo.filename}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={mediaUrl(photo.thumbnail_url)}
                alt={photo.filename}
                loading="lazy"
                decoding="async"
                width={photo.width ?? undefined}
                height={photo.height ?? undefined}
                className="w-full transition-opacity duration-200 group-hover:opacity-85"
              />
            </button>

            {scores?.[photo.id] !== undefined && (
              <figcaption className="pointer-events-none absolute left-2 top-2 rounded-full bg-ink/85 px-2 py-0.5 text-micro text-honey-bright">
                {Math.round(scores[photo.id] * 100)}% match
              </figcaption>
            )}

            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(photo)}
                className="absolute right-2 top-2 rounded-full bg-ink/85 px-2 py-1 text-micro text-chalk opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
                aria-label={`Delete ${photo.filename}`}
              >
                Delete
              </button>
            )}
          </figure>
        ))}
      </div>

      {openIndex !== null && (
        <PhotoViewer
          photos={photos}
          index={openIndex}
          onIndexChange={setOpenIndex}
          onClose={() => setOpenIndex(null)}
        />
      )}
    </>
  );
}

interface ViewerProps {
  photos: Photo[];
  index: number;
  onIndexChange: (index: number) => void;
  onClose: () => void;
}

export function PhotoViewer({ photos, index, onIndexChange, onClose }: ViewerProps) {
  const photo = photos[index];
  const [shareNote, setShareNote] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const touchStartX = useRef<number | null>(null);

  const go = useCallback(
    (delta: number) => {
      const next = index + delta;
      if (next >= 0 && next < photos.length) onIndexChange(next);
    },
    [index, photos.length, onIndexChange],
  );

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") go(1);
      if (event.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    // Stop the page behind the viewer from scrolling on touch devices.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [go, onClose]);

  const share = async () => {
    const url = mediaUrl(photo.original_url);
    // Web Share opens the native sheet on a phone, which is where guests are.
    if (navigator.share) {
      try {
        await navigator.share({ title: photo.filename, url });
        return;
      } catch {
        /* dismissed: fall through to copying */
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setShareNote("Link copied");
    } catch {
      setShareNote("Couldn't copy the link");
    }
    setTimeout(() => setShareNote(null), 2500);
  };

  if (!photo) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={photo.filename}
      className="fixed inset-0 z-50 flex flex-col bg-ink-sunken/98"
      onTouchStart={(event) => {
        touchStartX.current = event.touches[0].clientX;
      }}
      onTouchEnd={(event) => {
        if (touchStartX.current === null) return;
        const delta = event.changedTouches[0].clientX - touchStartX.current;
        if (Math.abs(delta) > 60) go(delta < 0 ? 1 : -1);
        touchStartX.current = null;
      }}
    >
      <header className="flex items-center justify-between gap-3 px-4 py-3">
        <p className="truncate text-sm text-chalk-soft">
          <span className="tnum">
            {index + 1} / {photos.length}
          </span>
          <span className="mx-2 text-line-bright">|</span>
          {photo.filename}
        </p>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          className="rounded-control px-3 py-1.5 text-sm text-chalk hover:bg-ink-raised"
        >
          Close
        </button>
      </header>

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-2">
        {index > 0 && (
          <button
            type="button"
            onClick={() => go(-1)}
            aria-label="Previous photo"
            className="absolute left-2 z-10 rounded-full bg-ink/70 p-3 text-chalk hover:bg-ink"
          >
            <Chevron direction="left" />
          </button>
        )}

        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={photo.id}
          src={mediaUrl(photo.original_url)}
          alt={photo.filename}
          className="max-h-full max-w-full object-contain"
        />

        {index < photos.length - 1 && (
          <button
            type="button"
            onClick={() => go(1)}
            aria-label="Next photo"
            className="absolute right-2 z-10 rounded-full bg-ink/70 p-3 text-chalk hover:bg-ink"
          >
            <Chevron direction="right" />
          </button>
        )}
      </div>

      <footer className="flex flex-wrap items-center justify-center gap-3 px-4 py-4">
        <a
          href={`${mediaUrl(photo.original_url)}?download=true`}
          download={photo.filename}
          className="inline-flex items-center rounded-control bg-honey px-5 py-2.5 text-sm font-semibold text-ink hover:bg-honey-bright"
        >
          Download
        </a>
        <Button variant="secondary" onClick={share}>
          Share
        </Button>
        {shareNote && <span className="text-sm text-chalk-soft">{shareNote}</span>}
      </footer>
    </div>
  );
}

function Chevron({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={cn("h-5 w-5", direction === "left" && "rotate-180")}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}
