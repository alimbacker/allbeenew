"use client";

/** Shared primitives. Both surfaces (ink and paper) are handled by variant. */
import { cn } from "@/lib/format";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  surface?: "ink" | "paper";
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  surface = "ink",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2.5 text-sm",
    lg: "px-6 py-3.5 text-base",
  };
  const variants = {
    primary: "bg-honey text-ink hover:bg-honey-bright font-semibold",
    secondary:
      surface === "ink"
        ? "border border-line bg-ink-raised text-chalk hover:border-line-bright"
        : "border border-bark/15 bg-paper-raised text-bark hover:border-bark/30",
    ghost:
      surface === "ink"
        ? "text-chalk-soft hover:bg-ink-raised hover:text-chalk"
        : "text-bark-soft hover:bg-paper-sunken hover:text-bark",
    danger: "border border-alert/40 text-alert hover:bg-alert/10",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        sizes[size],
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  surface?: "ink" | "paper";
};

export function Field({ label, hint, error, surface = "ink", id, className, ...rest }: FieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={inputId}
        className={cn("block text-sm", surface === "ink" ? "text-chalk" : "text-bark")}
      >
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        className={cn(
          "w-full rounded-control border px-3 py-2.5 text-base transition-colors",
          "focus:border-honey focus:outline-none",
          surface === "ink"
            ? "border-line bg-ink-sunken text-chalk placeholder:text-chalk-soft/50"
            : "border-bark/20 bg-paper-raised text-bark placeholder:text-bark-soft/50",
          error && "border-alert",
          className,
        )}
        {...rest}
      />
      {error ? (
        <p id={`${inputId}-error`} className="text-sm text-alert">
          {error}
        </p>
      ) : hint ? (
        <p
          id={`${inputId}-hint`}
          className={cn("text-sm", surface === "ink" ? "text-chalk-soft" : "text-bark-soft")}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Textarea({
  label,
  surface = "ink",
  id,
  ...rest
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  surface?: "ink" | "paper";
}) {
  const fieldId = id ?? `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={fieldId}
        className={cn("block text-sm", surface === "ink" ? "text-chalk" : "text-bark")}
      >
        {label}
      </label>
      <textarea
        id={fieldId}
        rows={3}
        className={cn(
          "w-full rounded-control border px-3 py-2.5 text-base focus:border-honey focus:outline-none",
          surface === "ink"
            ? "border-line bg-ink-sunken text-chalk placeholder:text-chalk-soft/50"
            : "border-bark/20 bg-paper-raised text-bark",
        )}
        {...rest}
      />
    </div>
  );
}

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded-panel border border-line bg-ink-raised", className)}>{children}</div>
  );
}

export function Alert({
  tone = "error",
  children,
}: {
  tone?: "error" | "info" | "success";
  children: React.ReactNode;
}) {
  const tones = {
    error: "border-alert/40 bg-alert/10 text-alert",
    info: "border-honey/40 bg-honey/10 text-honey-bright",
    success: "border-go/40 bg-go/10 text-go",
  };
  return (
    <div role="alert" className={cn("rounded-control border px-4 py-3 text-sm", tones[tone])}>
      {children}
    </div>
  );
}

export function LiveBadge({ label = "Live" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-go/40 bg-go/10 px-3 py-1 text-sm text-go">
      <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-go" aria-hidden />
      {label}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const tones: Record<string, string> = {
    READY: "border-go/40 text-go",
    PROCESSING: "border-honey/40 text-honey",
    UPLOADING: "border-honey/40 text-honey",
    FAILED: "border-alert/40 text-alert",
    LIVE: "border-go/40 text-go",
    ARCHIVED: "border-line-bright text-chalk-soft",
  };
  return (
    <span
      className={cn(
        "inline-block rounded-full border px-2.5 py-0.5 text-micro",
        tones[status] ?? "border-line-bright text-chalk-soft",
      )}
    >
      {status}
    </span>
  );
}

export function EmptyState({
  title,
  body,
  action,
  surface = "ink",
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  surface?: "ink" | "paper";
}) {
  return (
    <div
      className={cn(
        "rounded-panel border border-dashed px-6 py-14 text-center",
        surface === "ink" ? "border-line" : "border-bark/20",
      )}
    >
      <h3
        className={cn(
          "font-display text-lg font-semibold",
          surface === "ink" ? "text-chalk" : "text-bark",
        )}
      >
        {title}
      </h3>
      <p
        className={cn(
          "mx-auto mt-2 max-w-sm text-sm",
          surface === "ink" ? "text-chalk-soft" : "text-bark-soft",
        )}
      >
        {body}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/** Shown while a photo grid loads, matching the masonry rhythm. */
export function GridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="masonry" aria-hidden>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="relative overflow-hidden rounded-control bg-ink-raised"
          style={{ height: `${140 + ((index * 37) % 90)}px` }}
        >
          <div className="absolute inset-0 animate-sweep bg-gradient-to-r from-transparent via-white/5 to-transparent" />
        </div>
      ))}
    </div>
  );
}
