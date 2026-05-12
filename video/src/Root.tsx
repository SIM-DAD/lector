import React from 'react';
import { Composition } from 'remotion';
import { LectorDemo } from './LectorDemo';
import { LectorShort01, LECTOR_SHORT_01_FRAMES } from './shorts/LectorShort01';
import { FPS, TOTAL_FRAMES, W, H, V } from './tokens';

export const Root: React.FC = () => (
  <>
    {/* ── Horizontal (16:9) — website embed ──────────────────────── */}
    <Composition
      id="LectorDemo"
      component={LectorDemo}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={W}
      height={H}
    />

    {/* ── Vertical (9:16) — TikTok / YouTube Shorts ──────────────── */}
    <Composition
      id="LectorShort01"
      component={LectorShort01}
      durationInFrames={LECTOR_SHORT_01_FRAMES}
      fps={FPS}
      width={V.w}
      height={V.h}
    />
  </>
);
