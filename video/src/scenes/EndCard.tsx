import React from 'react';
import {
  AbsoluteFill, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import { C, FONT } from '../tokens';

export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sceneOp = interpolate(frame, [0, 16], [0, 1], { extrapolateRight: 'clamp' });

  const logoScale = spring({ frame, fps, config: { damping: 18, stiffness: 80 } });
  const logoOp    = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' });

  const tagOp = interpolate(frame, [16, 36], [0, 1], { extrapolateRight: 'clamp' });

  const ruleW = interpolate(
    spring({ frame: Math.max(0, frame - 28), fps, config: { damping: 24 } }),
    [0, 1], [0, 56],
  );

  const urlProgress = spring({
    frame: Math.max(0, frame - 36), fps,
    config: { damping: 20, stiffness: 100 },
  });
  const urlY  = interpolate(urlProgress, [0, 1], [16, 0]);
  const urlOp = interpolate(frame, [36, 52], [0, 1], { extrapolateRight: 'clamp' });

  const subOp = interpolate(frame, [50, 66], [0, 1], { extrapolateRight: 'clamp' });

  const badgeOp = interpolate(frame, [64, 82], [0, 1], { extrapolateRight: 'clamp' });
  const badgeY  = interpolate(
    spring({ frame: Math.max(0, frame - 64), fps, config: { damping: 20 } }),
    [0, 1], [10, 0],
  );

  return (
    <AbsoluteFill style={{
      background: C.bg,
      opacity: sceneOp,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: FONT,
    }}>

      {/* Logo + wordmark */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 22,
        marginBottom: 18,
        opacity: logoOp,
        transform: `scale(${logoScale})`,
      }}>
        <img src={staticFile('icon.svg')} style={{ width: 60, height: 60 }} />
        <span style={{
          fontSize: 60,
          fontWeight: 800,
          color: C.accent,
          letterSpacing: '-0.03em',
          lineHeight: 1,
        }}>
          Lector
        </span>
      </div>

      {/* Tagline */}
      <div style={{
        opacity: tagOp,
        fontSize: 20,
        fontWeight: 400,
        marginBottom: 28,
        letterSpacing: '0.01em',
      }}>
        <span style={{ color: C.muted }}>Write it. </span>
        <span style={{ color: C.accent, fontWeight: 700 }}>Hear</span>
        <span style={{ color: C.muted }}> it back.</span>
      </div>

      {/* Rule */}
      <div style={{
        width: ruleW,
        height: 3,
        background: C.accent,
        borderRadius: 2,
        marginBottom: 28,
      }} />

      {/* URL */}
      <div style={{
        opacity: urlOp,
        transform: `translateY(${urlY}px)`,
        marginBottom: 14,
      }}>
        <div style={{
          background: C.accent,
          color: C.white,
          padding: '12px 36px',
          borderRadius: 99,
          fontSize: 18,
          fontWeight: 700,
          letterSpacing: '0.01em',
        }}>
          uselector.app
        </div>
      </div>

      {/* Sub-CTA */}
      <div style={{
        opacity: subOp,
        fontSize: 14,
        color: C.muted,
        letterSpacing: '0.02em',
        marginBottom: 28,
      }}>
        Free for personal use · PolyForm Noncommercial License
      </div>

      {/* Feature badges */}
      <div style={{
        opacity: badgeOp,
        transform: `translateY(${badgeY}px)`,
        display: 'flex',
        gap: 12,
      }}>
        {['100% local', 'No cloud', 'Voice cloning · F5-TTS'].map((badge) => (
          <div key={badge} style={{
            padding: '5px 14px',
            border: `1px solid ${C.border}`,
            borderRadius: 99,
            fontSize: 12,
            fontWeight: 500,
            color: C.muted,
          }}>
            {badge}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
