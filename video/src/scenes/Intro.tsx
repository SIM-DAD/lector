import React from 'react';
import {
  AbsoluteFill, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import { C, FONT } from '../tokens';

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Icon fades + scales in
  const iconScale = spring({ frame, fps, config: { damping: 16, stiffness: 90 } });
  const iconOp    = interpolate(frame, [0, 16], [0, 1], { extrapolateRight: 'clamp' });

  // Wordmark slides up
  const wordProgress = spring({
    frame: Math.max(0, frame - 10), fps,
    config: { damping: 20, stiffness: 80 },
  });
  const wordY  = interpolate(wordProgress, [0, 1], [18, 0]);
  const wordOp = interpolate(frame, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // Tagline with bold accent word
  const tagOp = interpolate(frame, [28, 52], [0, 1], { extrapolateRight: 'clamp' });

  // Accent rule under wordmark
  const ruleW = interpolate(
    spring({ frame: Math.max(0, frame - 24), fps, config: { damping: 24 } }),
    [0, 1], [0, 52],
  );

  // Scene fade-out
  const sceneOut = interpolate(frame, [78, 90], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{
      background: C.darkBg,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: FONT,
      opacity: sceneOut,
    }}>

      {/* Icon + wordmark */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 26,
        marginBottom: 16,
        opacity: iconOp,
        transform: `scale(${iconScale})`,
      }}>
        <img src={staticFile('icon.svg')} style={{ width: 76, height: 76 }} />
        <div style={{
          opacity: wordOp,
          transform: `translateY(${wordY}px)`,
          fontSize: 80,
          fontWeight: 800,
          color: C.accent,
          letterSpacing: '-0.03em',
          lineHeight: 1,
        }}>
          Lector
        </div>
      </div>

      {/* Accent rule */}
      <div style={{
        width: ruleW,
        height: 3,
        background: C.accent,
        borderRadius: 2,
        marginBottom: 24,
      }} />

      {/* Tagline: "Write it. Hear it back." */}
      <div style={{
        opacity: tagOp,
        fontSize: 22,
        fontWeight: 400,
        letterSpacing: '0.01em',
      }}>
        <span style={{ color: C.darkMuted }}>Write it. </span>
        <span style={{ color: C.accent, fontWeight: 700 }}>Hear</span>
        <span style={{ color: C.darkMuted }}> it back.</span>
      </div>
    </AbsoluteFill>
  );
};
