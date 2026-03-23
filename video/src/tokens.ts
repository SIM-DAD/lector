import { loadFont } from '@remotion/google-fonts/PlusJakartaSans';

const { fontFamily } = loadFont();
export const FONT = fontFamily;

export const C = {
  bg:       '#FFFFFF',
  surface:  '#F7F7F8',
  text:     '#0F0F0F',
  accent:   '#5C4B8A',
  accentH:  '#4E3F7A',
  accentL:  '#EDE9F8',
  muted:    '#6B7280',
  border:   '#E4E4E7',
  white:    '#FFFFFF',
  darkBg:   '#0D0D12',
  darkSurf: '#16131F',
  darkText: '#E8E5F0',
  darkMuted:'rgba(232,229,240,0.55)',
} as const;

export const FPS          = 30;
export const W            = 1280;
export const H            = 720;
export const TOTAL_FRAMES = 720; // 24 s

// Absolute sequence timing
export const SEQ = {
  intro:    { from: 0,   duration: 90  }, // 0 – 3 s
  writing:  { from: 90,  duration: 240 }, // 3 – 11 s
  playback: { from: 330, duration: 240 }, // 11 – 19 s
  endCard:  { from: 570, duration: 150 }, // 19 – 24 s
} as const;

export const ANNOTATION = 'Interface elements may not accurately represent the final product design.';
