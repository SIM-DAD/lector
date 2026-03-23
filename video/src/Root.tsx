import React from 'react';
import { Composition } from 'remotion';
import { LectorDemo } from './LectorDemo';
import { FPS, TOTAL_FRAMES, W, H } from './tokens';

export const Root: React.FC = () => (
  <Composition
    id="LectorDemo"
    component={LectorDemo}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={W}
    height={H}
  />
);
