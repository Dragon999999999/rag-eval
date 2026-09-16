/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semantic design tokens
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        "surface-elevated": "var(--color-surface-elevated)",
        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",

        // Borders
        "border-default": "var(--color-border-default)",
        "border-strong": "var(--color-border-strong)",

        // Text
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "text-disabled": "var(--color-text-disabled)",

        // Accent (cool blue-purple)
        accent: "var(--color-accent)",
        "accent-hover": "var(--color-accent-hover)",
        "accent-active": "var(--color-accent-active)",
        "accent-subtle": "var(--color-accent-subtle)",

        // Status
        success: "var(--color-success)",
        "success-bg": "var(--color-success-bg)",
        warning: "var(--color-warning)",
        "warning-bg": "var(--color-warning-bg)",
        error: "var(--color-error)",
        "error-bg": "var(--color-error-bg)",
        info: "var(--color-info)",
        "info-bg": "var(--color-info-bg)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.5rem" }],
        lg: ["1rem", { lineHeight: "1.5rem" }],
        xl: ["1.125rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.25rem", { lineHeight: "1.75rem" }],
      },
      spacing: {
        18: "4.5rem",
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        md: "0.5rem",
        lg: "0.625rem",
      },
    },
  },
  plugins: [],
};
