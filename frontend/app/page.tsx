import Link from "next/link";
import { Logo } from "@/components/logo";

/**
 * The hero is the product's actual claim: the gap between the shutter and the
 * guest's phone, measured in seconds rather than days. Everything else on the
 * page is quiet so that stays the memorable thing.
 */
export default function LandingPage() {
  return (
    <main className="on-ink min-h-dvh bg-ink text-chalk">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <nav className="flex items-center gap-2">
          <Link
            href="/login"
            className="rounded-control px-4 py-2 text-sm text-chalk-soft hover:text-chalk"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-control bg-honey px-4 py-2 text-sm font-semibold text-ink hover:bg-honey-bright"
          >
            Create an account
          </Link>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-12 sm:pt-20">
        <h1 className="max-w-4xl font-display text-hero font-bold text-chalk">
          Your guests get their photos
          <br />
          before they leave the party.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-chalk-soft">
          Upload as you shoot. Guests scan one code, take one selfie, and find
          every frame they appear in. No app, no sign-up, no waiting three weeks
          for a gallery link.
        </p>

        <div className="mt-9 flex flex-wrap gap-3">
          <Link
            href="/register"
            className="rounded-control bg-honey px-6 py-3.5 font-semibold text-ink hover:bg-honey-bright"
          >
            Start your first event
          </Link>
          <Link
            href="/login"
            className="rounded-control border border-line px-6 py-3.5 hover:border-line-bright"
          >
            Sign in
          </Link>
        </div>

        {/* A real sequence, so it is numbered. */}
        <ol className="mt-20 grid gap-px overflow-hidden rounded-panel border border-line bg-line sm:grid-cols-3">
          {[
            {
              title: "Capture",
              body: "Shoot the event and upload straight from your laptop or the desktop uploader, which watches a folder and sends new frames on its own.",
            },
            {
              title: "Match",
              body: "Each photo is scanned for faces on your own server as it arrives. Nothing is sent to a cloud recognition service.",
            },
            {
              title: "Deliver",
              body: "A guest scans the table QR, takes a selfie, and downloads their photos. The gallery updates while they are still watching it.",
            },
          ].map((step, index) => (
            <li key={step.title} className="bg-ink p-7">
              <span className="tnum font-display text-sm text-honey">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h2 className="mt-3 font-display text-xl font-semibold text-chalk">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-chalk-soft">{step.body}</p>
            </li>
          ))}
        </ol>

        <p className="mt-10 max-w-xl text-sm leading-relaxed text-chalk-soft">
          Photos live on your own server. Face matching runs locally. You can
          move the whole thing to a different machine by copying one folder and
          one database.
        </p>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8 text-sm text-chalk-soft">
          <span>ALLBEE Instant — Capture. Match. Deliver.</span>
          <Link href="/docs" className="hover:text-chalk">
            Have an event code? Open it from the link your photographer shared.
          </Link>
        </div>
      </footer>
    </main>
  );
}
