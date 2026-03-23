import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { SEQ } from './tokens';
import { Intro }         from './scenes/Intro';
import { WritingScene }  from './scenes/WritingScene';
import { PlaybackScene } from './scenes/PlaybackScene';
import { EndCard }       from './scenes/EndCard';

export const LectorDemo: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={SEQ.intro.from}    durationInFrames={SEQ.intro.duration}>
      <Intro />
    </Sequence>
    <Sequence from={SEQ.writing.from}  durationInFrames={SEQ.writing.duration}>
      <WritingScene />
    </Sequence>
    <Sequence from={SEQ.playback.from} durationInFrames={SEQ.playback.duration}>
      <PlaybackScene />
    </Sequence>
    <Sequence from={SEQ.endCard.from}  durationInFrames={SEQ.endCard.duration}>
      <EndCard />
    </Sequence>
  </AbsoluteFill>
);
