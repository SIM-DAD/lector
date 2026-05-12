/**
 * ShortShell — vertical (9:16) canvas wrapper for Lector TikTok/Shorts content.
 *
 * Lector shorts use the dark writing-surface aesthetic throughout —
 * dark background with violet accent, matching the app's dark-mode editor.
 * Visually distinct from Ibis (light/blue) and TASS (dark/green).
 */
import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { C, FONT, V } from '../tokens';

const INTRO_FRAMES = 30;
const OUTRO_FRAMES = 45;

interface ShortShellProps {
  children: React.ReactNode;
  totalFrames: number;
  bg?: string;
}

const IntroCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const letterY = spring({ frame, fps, config: { damping: 24, stiffness: 70 } });

  return (
    <AbsoluteFill
      style={{
        background: C.darkBg,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          fontFamily: FONT,
          fontSize: 60,
          fontWeight: 800,
          color: C.accent,
          letterSpacing: '-0.02em',
          transform: `translateY(${interpolate(letterY, [0, 1], [30, 0])}px)`,
        }}
      >
        Lector
      </div>
      <div
        style={{
          fontFamily: FONT,
          fontSize: 16,
          fontWeight: 400,
          fontStyle: 'italic',
          color: C.darkMuted,
          marginTop: 10,
          opacity: interpolate(frame, [12, 24], [0, 1], { extrapolateRight: 'clamp' }),
        }}
      >
        Hear what you meant to write.
      </div>
    </AbsoluteFill>
  );
};

const OutroCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const spring1 = spring({ frame, fps, config: { damping: 20, stiffness: 80 } });

  return (
    <AbsoluteFill
      style={{
        background: C.darkBg,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          fontFamily: FONT,
          fontSize: 44,
          fontWeight: 800,
          color: C.accent,
          letterSpacing: '-0.02em',
          transform: `translateY(${interpolate(spring1, [0, 1], [16, 0])}px)`,
        }}
      >
        Lector
      </div>
      <div
        style={{
          fontFamily: FONT,
          fontSize: 14,
          fontWeight: 500,
          color: C.darkMuted,
          marginTop: 14,
          opacity: interpolate(frame, [15, 28], [0, 1], { extrapolateRight: 'clamp' }),
        }}
      >
        uselector.app
      </div>
    </AbsoluteFill>
  );
};

export const ShortShell: React.FC<ShortShellProps> = ({
  children,
  totalFrames,
  bg = C.darkBg,
}) => {
  const contentStart = INTRO_FRAMES;
  const contentDuration = totalFrames - INTRO_FRAMES - OUTRO_FRAMES;
  const outroStart = totalFrames - OUTRO_FRAMES;

  return (
    <AbsoluteFill style={{ background: bg }}>
      <Sequence from={0} durationInFrames={INTRO_FRAMES}>
        <IntroCard />
      </Sequence>
      <Sequence from={contentStart} durationInFrames={contentDuration}>
        {children}
      </Sequence>
      <Sequence from={outroStart} durationInFrames={OUTRO_FRAMES}>
        <OutroCard />
      </Sequence>
    </AbsoluteFill>
  );
};

export { INTRO_FRAMES, OUTRO_FRAMES };
