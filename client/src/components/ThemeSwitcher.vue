<template>
  <button
    class="theme-button"
    :aria-label="
      theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
    "
    :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
    @click="toggleTheme"
  >
    <svg
      v-if="theme === 'dark'"
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      class="theme-icon"
    >
      <circle
        cx="10"
        cy="10"
        r="3.5"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <path
        d="M10 2v2M10 16v2M2 10h2M16 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
      />
    </svg>
    <svg
      v-else
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      class="theme-icon"
    >
      <path
        d="M16.5 11.8A6.5 6.5 0 1 1 8.2 3.5a5.5 5.5 0 0 0 8.3 8.3z"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
      />
    </svg>
  </button>
</template>

<script setup>
import { useTheme } from "../composables/useTheme";

const { theme, toggleTheme } = useTheme();
</script>

<style scoped>
.theme-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  background: var(--color-surface, white);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--color-text-muted, #64748b);
  padding: 0;
}

.theme-button:hover {
  background: var(--color-surface-hover, #f8fafc);
  border-color: var(--color-border-strong, #cbd5e1);
  color: var(--color-text-strong, #0f172a);
}

.theme-button:focus-visible {
  outline: 2px solid var(--color-accent, #2563eb);
  outline-offset: 2px;
}

.theme-icon {
  flex-shrink: 0;
}
</style>
