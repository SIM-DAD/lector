import React from 'react';
import {
  AbsoluteFill, interpolate, spring,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import { C, FONT, ANNOTATION } from '../tokens';

const SENTENCES = [
  'Policy Analysis Report',
  'The proposed regulation would require all federal contractors to submit updated compliance documentation by the third quarter.',
  'Officials identified three primary concerns during the initial review: timeline, scope, and enforcement mechanisms.',
  'A final determination is expected before the legislative session concludes.',
];

// Each sentence plays for ~50 frames; starts appearing after a short delay
const SENTENCE_DURATION = 55;
const SENTENCE_START    = 18;

// Waveform bar heights (looping pattern)
const WAVE_HEIGHTS = [18, 28, 44, 36, 52, 40, 30, 48, 24, 36, 52, 42, 28, 38, 54, 34, 46, 26, 42, 50];

export const PlaybackScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Which sentence is highlighted
  const activeSentence = Math.min(
    SENTENCES.length - 1,
    Math.floor(Math.max(0, frame - SENTENCE_START) / SENTENCE_DURATION),
  );

  // Playback position 0→1
  const playProgress = interpolate(frame, [SENTENCE_START, 218], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // Timer: 00:00 → 00:18
  const secondsElapsed = Math.floor(playProgress * 18);
  const timeDisplay = `${String(Math.floor(secondsElapsed / 60)).padStart(2, '0')}:${String(secondsElapsed % 60).padStart(2, '0')}`;

  // Scene fade in
  const sceneOp = interpolate(frame, [0, 16], [0, 1], { extrapolateRight: 'clamp' });

  // Scene fade out
  const sceneOut = interpolate(frame, [228, 240], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // Voice panel slides in from right
  const panelX = interpolate(
    spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 22, stiffness: 80 } }),
    [0, 1], [200, 0],
  );
  const panelOp = interpolate(frame, [8, 28], [0, 1], { extrapolateRight: 'clamp' });

  // Waveform animation — bars pulse with playback
  const waveActive = frame >= SENTENCE_START && frame <= 200;

  return (
    <AbsoluteFill style={{
      background: C.darkBg,
      display: 'flex',
      flexDirection: 'column',
      fontFamily: FONT,
      opacity: Math.min(sceneOp, sceneOut),
    }}>

      {/* Toolbar */}
      <div style={{
        height: 48,
        background: C.darkSurf,
        borderBottom: `1px solid rgba(255,255,255,0.07)`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 32px',
        gap: 20,
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.accent, letterSpacing: '-0.01em' }}>
          Lector
        </span>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', marginLeft: 'auto' }}>
          policy-analysis.md
        </span>
        {/* Stop button (playing state) */}
        <div style={{
          padding: '5px 16px',
          borderRadius: 6,
          background: C.accent,
          fontSize: 12,
          fontWeight: 600,
          color: '#fff',
          cursor: 'default',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <div style={{ width: 8, height: 8, background: '#fff', borderRadius: 2 }} />
          Stop
        </div>
      </div>

      {/* Main content row */}
      <div style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden',
      }}>
        {/* Editor area */}
        <div style={{
          flex: 1,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: '56px 0',
          overflowY: 'hidden',
        }}>
          <div style={{ width: 640 }}>
            {SENTENCES.map((sentence, i) => {
              const isActive = i === activeSentence;
              const isPast   = i < activeSentence;
              const isH1     = i === 0;

              return (
                <div key={i} style={{ marginBottom: isH1 ? 28 : 18 }}>
                  <span style={{
                    fontSize: isH1 ? 28 : 16,
                    fontWeight: isH1 ? 700 : 400,
                    color: isActive ? C.darkText : (isPast ? 'rgba(232,229,240,0.35)' : 'rgba(232,229,240,0.55)'),
                    letterSpacing: isH1 ? '-0.02em' : '0.01em',
                    lineHeight: 1.75,
                    background: isActive ? `rgba(92,75,138,0.20)` : 'transparent',
                    borderRadius: 4,
                    padding: isActive ? '0 4px' : '0',
                    borderBottom: isActive ? `2px solid ${C.accent}` : '2px solid transparent',
                    transition: 'all 0.2s',
                  }}>
                    {sentence}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Voice panel */}
        <div style={{
          width: 220,
          background: C.darkSurf,
          borderLeft: `1px solid rgba(255,255,255,0.07)`,
          padding: '28px 20px',
          opacity: panelOp,
          transform: `translateX(${panelX}px)`,
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 18 }}>
            Voice
          </div>
          {['Default', 'Custom — Alex', 'Custom — Janet'].map((v, i) => (
            <div key={v} style={{
              padding: '8px 10px',
              borderRadius: 6,
              fontSize: 13,
              color: i === 0 ? C.accent : 'rgba(255,255,255,0.45)',
              background: i === 0 ? 'rgba(92,75,138,0.15)' : 'transparent',
              border: i === 0 ? `1px solid rgba(92,75,138,0.35)` : '1px solid transparent',
              marginBottom: 6,
              fontWeight: i === 0 ? 600 : 400,
              cursor: 'default',
            }}>
              {v}
            </div>
          ))}
          <div style={{ marginTop: 24, fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 12 }}>
            Speed
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {['0.75×', '1×', '1.25×'].map((s, i) => (
              <div key={s} style={{
                flex: 1,
                textAlign: 'center',
                padding: '5px 0',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: i === 1 ? 700 : 400,
                color: i === 1 ? C.accent : 'rgba(255,255,255,0.35)',
                background: i === 1 ? 'rgba(92,75,138,0.15)' : 'transparent',
                border: i === 1 ? `1px solid rgba(92,75,138,0.35)` : '1px solid transparent',
              }}>
                {s}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Playback bar */}
      <div style={{
        height: 64,
        background: C.darkSurf,
        borderTop: `1px solid rgba(255,255,255,0.07)`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 32px',
        gap: 20,
        flexShrink: 0,
      }}>
        {/* Play/pause icon (playing = pause icon) */}
        <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
          <div style={{ width: 3, height: 16, background: C.accent, borderRadius: 1 }} />
          <div style={{ width: 3, height: 16, background: C.accent, borderRadius: 1 }} />
        </div>

        {/* Time */}
        <div style={{ fontSize: 12, fontWeight: 600, color: C.accent, minWidth: 38 }}>
          {timeDisplay}
        </div>

        {/* Waveform */}
        <div style={{
          flex: 1,
          height: 40,
          display: 'flex',
          alignItems: 'center',
          gap: 3,
          overflow: 'hidden',
        }}>
          {WAVE_HEIGHTS.map((h, i) => {
            const barProgress = i / WAVE_HEIGHTS.length;
            const isPastBar   = barProgress < playProgress;
            const isActiveBar = Math.abs(barProgress - playProgress) < (1 / WAVE_HEIGHTS.length) * 1.5;

            // Animate active bar height
            const animatedH = waveActive && isActiveBar
              ? h * (1 + 0.3 * Math.sin(frame * 0.4 + i))
              : h;

            return (
              <div key={i} style={{
                flex: 1,
                height: animatedH,
                background: isPastBar ? C.accent : 'rgba(255,255,255,0.15)',
                borderRadius: 2,
                transition: 'height 0.05s',
              }} />
            );
          })}
        </div>

        {/* Duration */}
        <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', minWidth: 38, textAlign: 'right' }}>
          00:18
        </div>
      </div>

      {/* Annotation */}
      <div style={{
        position: 'absolute',
        bottom: 70,
        left: 0, right: 0,
        textAlign: 'center',
        fontSize: 11,
        color: 'rgba(255,255,255,0.2)',
        fontStyle: 'italic',
        fontFamily: FONT,
      }}>
        {ANNOTATION}
      </div>
    </AbsoluteFill>
  );
};
