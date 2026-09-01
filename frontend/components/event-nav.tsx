"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/format";

export function EventNav({ eventId }: { eventId: string }) {
  const pathname = usePathname();
  const base = `/dashboard/events/${eventId}`;
  const items = [
    { href: base, label: "Overview" },
    { href: `${base}/gallery`, label: "Gallery" },
    { href: `${base}/upload`, label: "Upload" },
    { href: `${base}/guests`, label: "Guests" },
    { href: `${base}/qr`, label: "QR code" },
    { href: `${base}/settings`, label: "Settings" },
  ];

  return (
    <nav className="-mx-1 flex gap-1 overflow-x-auto border-b border-line pb-px">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
              active
                ? "border-honey text-chalk"
                : "border-transparent text-chalk-soft hover:text-chalk",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
