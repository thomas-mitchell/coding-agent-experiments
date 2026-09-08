import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/PressStart2P";
import { ENEMY_SHIP, PixelSprite, Starfield, makeStars } from "./pixels";

const { fontFamily } = loadFont();
const stars = makeStars(150, 8642);

export const WarpScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill name="Warp" style={{ backgroundColor: "#000000", fontFamily }}>
      <Interactive.Div
        name="Nebula"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(60% 60% at 50% 50%, rgba(28,42,140,0.55) 0%, rgba(0,0,0,0) 70%)",
          opacity: interpolate(frame, [0, 0.5 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      />

      <svg
        width="1920"
        height="1080"
        viewBox="0 0 1920 1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <Starfield
          stars={stars}
          time={frame / 62}
          streak={0.02 + (frame / 80) * 0.05}
        />
        <PixelSprite
          rows={ENEMY_SHIP}
          size={9}
          x={520}
          y={300}
          opacity={frame > 26 ? 1 : 0}
        />
        <PixelSprite
          rows={ENEMY_SHIP}
          size={13}
          x={1430}
          y={410}
          opacity={frame > 34 ? 1 : 0}
        />
        <PixelSprite
          rows={ENEMY_SHIP}
          size={20}
          x={1180}
          y={790}
          opacity={frame > 44 ? 1 : 0}
        />
      </svg>

      <Interactive.Div
        name="Alert wash"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(255,59,48,0.4) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 78%, rgba(255,59,48,0.4) 100%)",
          opacity: interpolate(frame % 24, [0, 12, 24], [0.2, 1, 0.2], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.4, 0, 0.6, 1),
          }),
        }}
      />

      <Interactive.Div
        name="Line one"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 400,
          textAlign: "center",
          color: "#ffd21e",
          fontSize: 116,
          lineHeight: 1.3,
          textShadow: "6px 0 0 rgba(255,59,48,0.75), -6px 0 0 rgba(63,208,255,0.75)",
          opacity: interpolate(frame, [16, 19], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [16, 26], [1.35, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        THE ZYLONS
      </Interactive.Div>

      <Interactive.Div
        name="Line two"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 560,
          textAlign: "center",
          color: "#ff3b30",
          fontSize: 116,
          lineHeight: 1.3,
          textShadow: "6px 0 0 rgba(255,210,30,0.6), -6px 0 0 rgba(63,208,255,0.6)",
          opacity: interpolate(frame, [30, 33], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [30, 40], [1.35, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        ARE COMING
      </Interactive.Div>
    </AbsoluteFill>
  );
};
