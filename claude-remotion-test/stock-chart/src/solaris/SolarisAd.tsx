import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { CrtScreen } from "./CrtScreen";
import { WarpScene } from "./WarpScene";
import { MapScene } from "./MapScene";
import { BattleScene } from "./BattleScene";
import { LogoScene } from "./LogoScene";

export const SolarisAd: React.FC = () => {
  return (
    <CrtScreen>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={80} name="Warp">
          <WarpScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={fade()}
          timing={linearTiming({ durationInFrames: 7 })}
        />
        <TransitionSeries.Sequence durationInFrames={80} name="Sector map">
          <MapScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={fade()}
          timing={linearTiming({ durationInFrames: 7 })}
        />
        <TransitionSeries.Sequence durationInFrames={80} name="Battle">
          <BattleScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={fade()}
          timing={linearTiming({ durationInFrames: 7 })}
        />
        <TransitionSeries.Sequence durationInFrames={81} name="Logo">
          <LogoScene />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </CrtScreen>
  );
};
