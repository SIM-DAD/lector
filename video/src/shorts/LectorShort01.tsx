/**
 * LectorShort01 — Placeholder vertical composition.
 * Replace content area with unique scene content for each Short.
 */
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { C, FONT, V } from '../tokens';
import { ShortShell } from './ShortShell';

export const LECTOR_SHORT_01_FRAMES = 300;

export const LectorShort01: React.FC = () => (
  <ShortShell totalFrames={LECTOR_SHORT_01_FRAMES}>
    <PlaceholderContent />
  </ShortShell>
);

const PlaceholderContent: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        background: C.darkBg,
        justifyContent: 'center',
        alignItems: 'center',
        padding: V.safeSide,
        paddingTop: V.safeTop,
        paddingBottom: V.safeBottom,
        opacity,
      }}
    >
      <div style={{ fontFamily: FONT, fontSize: 28, fontWeight: 800, color: C.darkText, textAlign: 'center', letterSpacing: '-0.02em', lineHeight: 1.3, maxWidth: 600 }}>
        [Scene content goes here]
      </div>
      <div style={{ fontFamily: FONT, fontSize: 14, color: C.darkMuted, marginTop: 16, textAlign: 'center' }}>
        1080 &times; 1920 &middot; 9:16 vertical
      </div>
    </AbsoluteFill>
  );
};
