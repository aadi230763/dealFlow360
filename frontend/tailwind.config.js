/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--color-canvas)",
        canvas: "var(--color-canvas)",
        surface: "var(--color-surface)",
        "surface-elevated": "var(--surface-elevated)",
        border: "var(--color-border)",
        ink: "var(--color-ink)",
        "ink-muted": "var(--color-ink-muted)",
        "ink-faint": "var(--color-ink-faint)",
        primary: "var(--color-accent)",
        "primary-hover": "var(--color-accent-hover)",
        "primary-bg": "var(--primary-bg)",
        accent: "var(--color-accent)",
        success: "var(--color-healthy)",
        "success-bg": "var(--color-healthy-bg)",
        healthy: "var(--color-healthy)",
        warning: "var(--color-warning)",
        "warning-bg": "var(--color-warning-bg)",
        danger: "var(--color-risk)",
        "danger-bg": "var(--color-risk-bg)",
        risk: "var(--color-risk)",
        "risk-bg": "var(--color-risk-bg)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      fontFeatureSettings: {
        tabular: '"tnum"',
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
      },
      borderRadius: {
        DEFAULT: "6px",
      },
    },
  },
  plugins: [],
};
