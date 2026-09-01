import { cn } from "@/lib/format";

/**
 * The mark is a hexagon -- a honeycomb cell, and also the shape of an aperture
 * blade array. It carries both halves of the name without spelling either out.
 */
export function Logo({
  className,
  showTagline = false,
  surface = "ink",
}: {
  className?: string;
  showTagline?: boolean;
  surface?: "ink" | "paper";
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden>
        <path
          d="M16 2.5 28 9.25v13.5L16 29.5 4 22.75V9.25z"
          fill="none"
          stroke="#F0A500"
          strokeWidth="2.25"
          strokeLinejoin="round"
        />
        <circle cx="16" cy="16" r="4.5" fill="#F0A500" />
      </svg>
      <div className="leading-none">
        <div
          className={cn(
            "font-display text-lg font-bold tracking-tight",
            surface === "ink" ? "text-chalk" : "text-bark",
          )}
        >
          ALLBEE <span className="text-honey">Instant</span>
        </div>
        {showTagline && (
          <div
            className={cn(
              "mt-1 text-sm",
              surface === "ink" ? "text-chalk-soft" : "text-bark-soft",
            )}
          >
            Capture. Match. Deliver.
          </div>
        )}
      </div>
    </div>
  );
}
