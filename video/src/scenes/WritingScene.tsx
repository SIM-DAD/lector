import React from 'react';
import {
  AbsoluteFill, interpolate,
  useCurrentFrame,
} from 'remotion';
import { C, FONT, ANNOTATION } from '../tokens';

// The text that gets "typed" on screen, sentence by sentence
const FULL_TEXT = [
  { type: 'h1',  content: 'Policy Analysis Report' },
  { type: 'p',   content: 'The proposed regulation would require all federal contractors to submit updated compliance documentation by the third quarter.' },
  { type: 'p',   content: 'Officials identified three primary concerns during the initial review: timeline, scope, and enforcement mechanisms.' },
  { type: 'p',   content: 'A final determination is expected before the legislative session concludes in ' },
];

// Flat string for typewriter effect
const FLAT_TEXT = 'Policy Analysis Report\n\nThe proposed regulation would require all federal contractors to submit updated compliance documentation by the third quarter.\n\nOfficials identified three primary concerns during the initial review: timeline, scope, and enforcement mechanisms.\n\nA final determination is expected before the legislative session concludes in ';

const TYPE_START  = 15;  // frame when typing begins
const CHARS_PER_F = 0.75; // characters per frame

export const WritingScene: React.FC = () => {
  const frame = useCurrentFrame();

  // How many chars are visible
  const charsVisible = Math.floor(Math.max(0, frame - TYPE_START) * CHARS_PER_F);
  const displayText  = FLAT_TEXT.slice(0, charsVisible);

  // Cursor blink (every 18 frames)
  const cursorOn = Math.floor(frame / 18) % 2 === 0;

  // Scene fade in
  const sceneOp = interpolate(frame, [0, 16], [0, 1], { extrapolateRight: 'clamp' });

  // Scene fade out
  const sceneOut = interpolate(frame, [228, 240], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // Parse display text into styled lines
  const lines = displayText.split('\n');

  return (
    <AbsoluteFill style={{
      background: C.darkBg,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: FONT,
      opacity: Math.min(sceneOp, sceneOut),
    }}>

      {/* Minimal toolbar */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: 48,
        background: C.darkSurf,
        borderBottom: `1px solid rgba(255,255,255,0.07)`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 32px',
        gap: 20,
      }}>
        <span style={{
          fontSize: 15,
          fontWeight: 700,
          color: C.accent,
          letterSpacing: '-0.01em',
        }}>
          Lector
        </span>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', marginLeft: 'auto' }}>
          policy-analysis.md
        </span>
        <div style={{
          padding: '5px 16px',
          borderRadius: 6,
          border: `1px solid ${C.accent}`,
          fontSize: 12,
          fontWeight: 600,
          color: C.accent,
          cursor: 'default',
        }}>
          Listen
        </div>
      </div>

      {/* Editor area */}
      <div style={{
        marginTop: 48,
        width: '100%',
        height: 'calc(100% - 48px)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'flex-start',
        padding: '60px 0',
        overflowY: 'hidden',
      }}>
        <div style={{
          width: 680,
          fontFamily: FONT,
          lineHeight: 1.75,
        }}>
          {lines.map((line, i) => {
            const isLast = i === lines.length - 1;
            const isH1   = i === 0 && line.length > 0;

            if (line === '') {
              return <div key={i} style={{ height: isH1 ? 28 : 18 }} />;
            }

            return (
              <div key={i} style={{
                fontSize: isH1 ? 28 : 16,
                fontWeight: isH1 ? 700 : 400,
                color: isH1 ? C.darkText : 'rgba(232,229,240,0.80)',
                letterSpacing: isH1 ? '-0.02em' : '0.01em',
                display: 'inline',
              }}>
                {line}
                {isLast && (
                  <span style={{
                    display: 'inline-block',
                    width: 2,
                    height: isH1 ? 28 : 18,
                    background: C.accent,
                    marginLeft: 2,
                    verticalAlign: 'middle',
                    opacity: cursorOn ? 1 : 0,
                  }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Annotation */}
      <div style={{
        position: 'absolute',
        bottom: 16,
        left: 0, right: 0,
        textAlign: 'center',
        fontSize: 11,
        color: 'rgba(255,255,255,0.3)',
        fontStyle: 'italic',
        fontFamily: FONT,
      }}>
        {ANNOTATION}
      </div>
    </AbsoluteFill>
  );
};
