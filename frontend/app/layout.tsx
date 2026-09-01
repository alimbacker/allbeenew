import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/lib/auth";

// Fonts are self-hosted from npm rather than pulled from Google at build time.
// ALLBEE is meant to be deployable to a private or air-gapped server, and
// `next/font/google` makes the *build* depend on an outside network call --
// which would be a strange dependency for a product whose whole premise is
// that nothing leaves your own machine. These resolve from node_modules and
// are emitted into the bundle, so the site also loads no third-party assets
// at runtime.
import "@fontsource/archivo/500.css";
import "@fontsource/archivo/600.css";
import "@fontsource/archivo/700.css";
import "@fontsource-variable/inter";

import "./globals.css";

export const metadata: Metadata = {
  title: "ALLBEE Instant — Capture. Match. Deliver.",
  description:
    "Event photography delivered while the event is still happening. Guests scan a QR code, take a selfie, and get their photos on the spot.",
};

export const viewport: Viewport = {
  themeColor: "#14120E",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
