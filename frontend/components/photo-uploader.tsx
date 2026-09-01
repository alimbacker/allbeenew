"use client";

/**
 * Photo uploader.
 *
 * Files are sent one per request with a small concurrency window rather than
 * as one giant multipart body. That costs a few more round trips and buys
 * three things that matter at a live event: a real per-file progress figure,
 * a failure that affects one frame instead of the whole batch, and retries
 * that do not re-send hundreds of megabytes.
 */
import { useCallback, useRef, useState } from "react";
import { uploadPhotos } from "@/lib/api";
import { Button, Alert } from "@/components/ui";
import { cn, formatBytes } from "@/lib/format";

const CONCURRENCY = 3;
const ACCEPT = "image/jpeg,image/png,image/webp";

type ItemState = "waiting" | "uploading" | "done" | "duplicate" | "failed";

interface Item {
  id: string;
  file: File;
  state: ItemState;
  progress: number;
  message?: string;
}

export function PhotoUploader({
  eventId,
  onUploaded,
}: {
  eventId: string;
  onUploaded?: () => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [running, setRunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const update = useCallback((id: string, patch: Partial<Item>) => {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }, []);

  const addFiles = useCallback((files: FileList | File[]) => {
    const accepted = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (!accepted.length) {
      setError("Those files aren't images. Add JPG, PNG or WEBP files.");
      return;
    }
    setError(null);
    setItems((current) => [
      ...current,
      ...accepted.map((file) => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
        file,
        state: "waiting" as ItemState,
        progress: 0,
      })),
    ]);
  }, []);

  const start = useCallback(async () => {
    const queue = items.filter((item) => item.state === "waiting" || item.state === "failed");
    if (!queue.length) return;

    setRunning(true);
    setError(null);
    let cursor = 0;

    const worker = async () => {
      while (cursor < queue.length) {
        const item = queue[cursor++];
        update(item.id, { state: "uploading", progress: 0, message: undefined });
        try {
          const response = await uploadPhotos(eventId, [item.file], (loaded, total) => {
            update(item.id, { progress: total ? loaded / total : 0 });
          });
          const outcome = response.results[0];
          if (outcome?.status === "duplicate") {
            update(item.id, { state: "duplicate", progress: 1, message: "Already uploaded" });
          } else if (outcome?.status === "rejected") {
            update(item.id, {
              state: "failed",
              progress: 0,
              message: outcome.error ?? "Rejected",
            });
          } else {
            update(item.id, { state: "done", progress: 1 });
          }
        } catch (err) {
          update(item.id, {
            state: "failed",
            progress: 0,
            message: err instanceof Error ? err.message : "Upload failed",
          });
        }
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    setRunning(false);
    onUploaded?.();
  }, [items, eventId, update, onUploaded]);

  const counts = items.reduce(
    (acc, item) => ({ ...acc, [item.state]: (acc[item.state] ?? 0) + 1 }),
    {} as Record<ItemState, number>,
  );
  const pending = (counts.waiting ?? 0) + (counts.failed ?? 0);
  const overall = items.length
    ? items.reduce((sum, item) => sum + item.progress, 0) / items.length
    : 0;

  return (
    <div className="space-y-5">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          addFiles(event.dataTransfer.files);
        }}
        className={cn(
          "rounded-panel border-2 border-dashed px-6 py-12 text-center transition-colors",
          dragging ? "border-honey bg-honey/5" : "border-line",
        )}
      >
        <p className="font-display text-lg font-semibold text-chalk">
          Drop photos here
        </p>
        <p className="mt-1 text-sm text-chalk-soft">JPG, PNG or WEBP</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => {
            if (event.target.files) addFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <div className="mt-5">
          <Button variant="secondary" onClick={() => inputRef.current?.click()}>
            Choose photos
          </Button>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {items.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-chalk-soft">
              <span className="tnum">{items.length}</span> selected
              {counts.done ? (
                <>
                  {" · "}
                  <span className="tnum text-go">{counts.done}</span> uploaded
                </>
              ) : null}
              {counts.duplicate ? (
                <>
                  {" · "}
                  <span className="tnum">{counts.duplicate}</span> already there
                </>
              ) : null}
              {counts.failed ? (
                <>
                  {" · "}
                  <span className="tnum text-alert">{counts.failed}</span> failed
                </>
              ) : null}
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setItems([])} disabled={running}>
                Clear
              </Button>
              <Button onClick={start} loading={running} disabled={!pending}>
                {counts.failed && !counts.waiting
                  ? `Retry ${counts.failed}`
                  : `Upload ${pending}`}
              </Button>
            </div>
          </div>

          {running && (
            <div
              className="h-1.5 overflow-hidden rounded-full bg-ink-sunken"
              role="progressbar"
              aria-valuenow={Math.round(overall * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full bg-honey transition-[width] duration-200"
                style={{ width: `${overall * 100}%` }}
              />
            </div>
          )}

          <ul className="max-h-96 divide-y divide-line overflow-y-auto rounded-panel border border-line">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="min-w-0 flex-1 truncate text-sm text-chalk">
                  {item.file.name}
                </span>
                <span className="tnum shrink-0 text-micro text-chalk-soft">
                  {formatBytes(item.file.size)}
                </span>
                <span className="w-28 shrink-0 text-right text-sm">
                  <StateLabel item={item} />
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function StateLabel({ item }: { item: Item }) {
  switch (item.state) {
    case "done":
      return <span className="text-go">Uploaded</span>;
    case "duplicate":
      return <span className="text-chalk-soft">Already there</span>;
    case "failed":
      return (
        <span className="text-alert" title={item.message}>
          {item.message?.slice(0, 16) ?? "Failed"}
        </span>
      );
    case "uploading":
      return <span className="tnum text-honey">{Math.round(item.progress * 100)}%</span>;
    default:
      return <span className="text-chalk-soft">Waiting</span>;
  }
}
