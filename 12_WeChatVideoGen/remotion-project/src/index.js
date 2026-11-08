import { registerRoot, Composition } from 'remotion';
import { VideoComposition, TOTAL_FRAMES } from './Composition.js';

const RemotionRoot = () => {
  return (
    <Composition
      id="Main"
      component={VideoComposition}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1600}
      height={1000}
    />
  );
};

registerRoot(RemotionRoot);
