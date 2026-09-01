import type { Config } from "tailwindcss";

/**
 * Two surfaces, chosen for where each is actually used.
 *
 * The photographer works in a dim reception hall for six hours, so the
 * dashboard is dark: photos read true against it and the screen is not a
 * torch. Guests are outdoors in daylight on a phone, so their pages are
 * light, where a dark UI would be unreadable.
 *
 * The neutrals are warm rather than blue-grey -- closer to a darkroom
 * safelight than to a generic near-black.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#14120E", // page behind the dashboard
          raised: "#1E1B16", // cards and panels
          sunken: "#0E0C09", // wells, gallery backdrop
        },
        line: {
          DEFAULT: "#332E25",
          bright: "#4A4234",
        },
        honey: {
          DEFAULT: "#F0A500",
          bright: "#FFD23F",
          dim: "#8A5F00",
        },
        paper: {
          DEFAULT: "#FAF7F0", // guest pages
          raised: "#FFFFFF",
          sunken: "#F0EBE0",
        },
        bark: {
          DEFAULT: "#2A2419", // body text on paper
          soft: "#6B6151",
        },
        chalk: {
          DEFAULT: "#F5F1E8", // body text on ink
          soft: "#A39A8A",
        },
        alert: "#E5484D",
        go: "#46A758",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      fontSize: {
        // A modular scale at ~1.25, so headings relate rather than jump.
        micro: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
        readout: ["1.75rem", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        counter: ["2.75rem", { lineHeight: "1", letterSpacing: "-0.03em" }],
        hero: ["clamp(2.5rem, 7vw, 4.5rem)", { lineHeight: "0.95", letterSpacing: "-0.035em" }],
      },
      borderRadius: {
        // Hierarchy through radius: panels are softer than controls.
        control: "0.5rem",
        panel: "1rem",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.35", transform: "scale(0.85)" },
        },
        sweep: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        riseIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-dot": "pulseDot 1.8s ease-in-out infinite",
        sweep: "sweep 1.4s ease-in-out infinite",
        "rise-in": "riseIn 0.25s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
