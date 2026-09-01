"use client";

/**
 * Selfie capture for guests.
 *
 * Uses getUserMedia where available and falls back to a file input with
 * `capture="user"`, which opens the phone's own camera app. Every path is
 * available without an account and works one-handed.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Alert, Spinner } from "@/components/ui";

const MAX_EDGE = 1080;
const JPEG_QUALITY = 0.9;

interface Props {
  onCapture: (blob: Blob, previewUrl: string) => void;
  busy?: boolean;
}

export function SelfieCapture({ onCapture, busy = false }: Props) {
  const [mode, setMode] = useState<"idle" | "camera">("idle");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => stopCamera, [stopCamera]);

  const startCamera = async () => {
    setError(null);
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 1280 } },
        audio: false,
      });
      streamRef.current = stream;
      setMode("camera");
      // The <video> only exists after the state flip, so attach on the next tick.
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      });
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      setError(
        name === "NotAllowedError"
          ? "Camera access was blocked. Allow it in your browser settings, or upload a photo instead."
          : "No camera available here. Upload a photo instead.",
      );
    } finally {
      setStarting(false);
    }
  };

  const shoot = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;

    const scale = Math.min(1, MAX_EDGE / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);

    const context = canvas.getContext("2d");
    if (!context) return;
    // Un-mirror: the preview is flipped so it feels like a mirror, but the
    // stored image must be the real orientation for matching.
    context.translate(canvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError("Couldn't capture that frame. Try again.");
          return;
        }
        stopCamera();
        setMode("idle");
        onCapture(blob, URL.createObjectURL(blob));
      },
      "image/jpeg",
      JPEG_QUALITY,
    );
  };

  if (mode === "camera") {
    return (
      <div className="space-y-4">
        <div className="relative overflow-hidden rounded-panel bg-bark">
          <video
            ref={videoRef}
            playsInline
            muted
            className="aspect-square w-full scale-x-[-1] object-cover"
          />
          <div
            className="pointer-events-none absolute inset-0 m-auto aspect-square w-2/3 rounded-full border-2 border-white/60"
            aria-hidden
          />
        </div>
        <div className="flex gap-3">
          <Button size="lg" className="flex-1" onClick={shoot} disabled={busy}>
            Take photo
          </Button>
          <Button
            variant="secondary"
            surface="paper"
            size="lg"
            onClick={() => {
              stopCamera();
              setMode("idle");
            }}
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}

      <Button size="lg" className="w-full" onClick={startCamera} loading={starting} disabled={busy}>
        Take a selfie
      </Button>

      <div className="flex items-center gap-3 text-sm text-bark-soft">
        <span className="h-px flex-1 bg-bark/15" />
        or
        <span className="h-px flex-1 bg-bark/15" />
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="user"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onCapture(file, URL.createObjectURL(file));
          event.target.value = "";
        }}
      />
      <Button
        variant="secondary"
        surface="paper"
        size="lg"
        className="w-full"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
      >
        Upload a photo
      </Button>

      {busy && (
        <p className="flex items-center justify-center gap-2 text-sm text-bark-soft">
          <Spinner className="h-4 w-4" />
          Looking through the photos
        </p>
      )}
    </div>
  );
}
