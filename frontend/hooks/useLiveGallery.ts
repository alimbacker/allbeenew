"use client";

/**
 * Live gallery feed.
 *
 * Prefers Server-Sent Events and silently falls back to polling when the
 * stream cannot be held open -- some mobile networks and corporate proxies
 * close idle connections. Both paths produce the same state, so callers never
 * branch on which one is active.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Photo } from "@/types";

const PAGE_SIZE = 48;
const POLL_INTERVAL_MS = 8000;

export type Connection = "connecting" | "live" | "polling" | "offline";

export function useLiveGallery(eventCode: string) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");

  const seen = useRef<Set<string>>(new Set());
  const offset = useRef(0);

  const absorb = useCallback((incoming: Photo[], append: boolean) => {
    setPhotos((current) => {
      const fresh = incoming.filter((photo) => !seen.current.has(photo.id));
      fresh.forEach((photo) => seen.current.add(photo.id));
      if (!fresh.length) return current;
      return append ? [...current, ...fresh] : [...fresh, ...current];
    });
  }, []);

  const loadFirstPage = useCallback(async () => {
    try {
      const page = await api.publicPhotos(eventCode, PAGE_SIZE, 0);
      seen.current = new Set(page.items.map((photo) => photo.id));
      setPhotos(page.items);
      setTotal(page.total);
      setHasMore(page.has_more);
      offset.current = page.items.length;
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load photos");
      setConnection("offline");
    } finally {
      setLoading(false);
    }
  }, [eventCode]);

  const loadMore = useCallback(async () => {
    const page = await api.publicPhotos(eventCode, PAGE_SIZE, offset.current);
    absorb(page.items, true);
    offset.current += page.items.length;
    setTotal(page.total);
    setHasMore(page.has_more);
  }, [eventCode, absorb]);

  /** Fetch only what is newer than the newest photo we already hold. */
  const refreshHead = useCallback(async () => {
    try {
      const page = await api.publicPhotos(eventCode, PAGE_SIZE, 0);
      absorb(page.items, false);
      setTotal(page.total);
      offset.current = Math.max(offset.current, page.items.length);
    } catch {
      /* transient: the next tick will retry */
    }
  }, [eventCode, absorb]);

  useEffect(() => {
    void loadFirstPage();
  }, [loadFirstPage]);

  useEffect(() => {
    let source: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let closed = false;

    const startPolling = () => {
      if (closed || pollTimer) return;
      setConnection("polling");
      pollTimer = setInterval(() => void refreshHead(), POLL_INTERVAL_MS);
    };

    try {
      source = new EventSource(api.streamUrl(eventCode));
      source.addEventListener("connected", () => setConnection("live"));
      // A photo becomes visible to guests only once it is READY.
      source.addEventListener("photo.ready", () => void refreshHead());
      source.addEventListener("photo.deleted", (event) => {
        const { id } = JSON.parse((event as MessageEvent).data);
        seen.current.delete(id);
        setPhotos((current) => current.filter((photo) => photo.id !== id));
        setTotal((value) => Math.max(0, value - 1));
      });
      source.onerror = () => {
        source?.close();
        source = null;
        startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      closed = true;
      source?.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [eventCode, refreshHead]);

  return { photos, total, hasMore, loading, error, connection, loadMore, refresh: refreshHead };
}
