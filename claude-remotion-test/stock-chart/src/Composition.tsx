import { Composition, Folder } from "remotion";
import { StockChart } from "./stock-chart/StockChart";
import { SolarisAd } from "./solaris/SolarisAd";
import { WarpScene } from "./solaris/WarpScene";
import { MapScene } from "./solaris/MapScene";
import { BattleScene } from "./solaris/BattleScene";
import { LogoScene } from "./solaris/LogoScene";

export const MyComposition = () => {
  return (
    <>
      <Composition
        id="StockChart"
        component={StockChart}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="SolarisAd"
        component={SolarisAd}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
      <Folder name="SolarisAd-Scenes">
        <Composition
          id="Solaris-Warp"
          component={WarpScene}
          durationInFrames={80}
          fps={30}
          width={1920}
          height={1080}
        />
        <Composition
          id="Solaris-Map"
          component={MapScene}
          durationInFrames={80}
          fps={30}
          width={1920}
          height={1080}
        />
        <Composition
          id="Solaris-Battle"
          component={BattleScene}
          durationInFrames={80}
          fps={30}
          width={1920}
          height={1080}
        />
        <Composition
          id="Solaris-Logo"
          component={LogoScene}
          durationInFrames={81}
          fps={30}
          width={1920}
          height={1080}
        />
      </Folder>
    </>
  );
};
