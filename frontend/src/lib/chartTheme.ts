import type { ColorScheme } from '../hooks/useColorScheme';

export interface ChartTheme {
  text: string;
  grid: string;
  accent: string;
  danger: string;
}

export const THEMES: Record<ColorScheme, ChartTheme> = {
  light: { text: '#0f172a', grid: '#e2e8f0', accent: '#1d4ed8', danger: '#b91c1c' },
  dark: { text: '#e5e7eb', grid: '#2b3956', accent: '#60a5fa', danger: '#f87171' },
};
