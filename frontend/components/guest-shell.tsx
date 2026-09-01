import { Logo } from "@/components/logo";

/** Page frame for every guest-facing screen: light surface, centred, phone-first. */
export function GuestShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="on-paper min-h-dvh bg-paper px-5 pb-16 pt-6 text-bark">
      <header className="mx-auto flex max-w-2xl justify-center">
        <Logo surface="paper" />
      </header>
      {children}
    </main>
  );
}
