import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/PressStart2P";
import {
  ENEMY_SHIP,
  PALETTE,
  PixelBurst,
  PixelSprite,
  PLAYER_SHIP,
  Starfield,
  makeStars,
} from "./pixels";

const { fontFamily } = loadFont();
const stars = makeStars(110, 20486);

export const BattleScene: React.FC = () => {
  const frame = useCurrentFrame();

  const playerX = interpolate(frame, [4, 16, 30, 44], [960, 700, 700, 1240], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.5, 0, 0.3, 1),
  });

  return (
    <AbsoluteFill
      name="Battle"
      style={{ backgroundColor: "#000000", fontFamily }}
    >
      <Interactive.Div
        name="Shake"
        style={{
          position: "absolute",
          inset: 0,
          translate: interpolate(
            frame,
            [28, 30, 32, 34, 36, 54, 56, 58, 60, 62],
            [
              "0px 0px",
              "18px -14px",
              "-15px 11px",
              "9px -7px",
              "0px 0px",
              "0px 0px",
              "20px 13px",
              "-16px -10px",
              "8px 6px",
              "0px 0px",
            ],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.linear,
            },
          ),
        }}
      >
        <Interactive.Div
          name="Muzzle wash"
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(50% 40% at 50% 100%, rgba(255,159,46,0.35) 0%, rgba(0,0,0,0) 70%)",
          }}
        />

        <svg
          width="1920"
          height="1080"
          viewBox="0 0 1920 1080"
          style={{ position: "absolute", inset: 0 }}
        >
          <Starfield stars={stars} time={frame / 42} streak={0.06} />

          {frame < 30 ? (
            <PixelSprite
              rows={ENEMY_SHIP}
              size={interpolate(frame, [0, 30], [11, 24], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              x={interpolate(frame, [0, 30], [640, 700], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              y={interpolate(frame, [0, 30], [330, 470], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
            />
          ) : null}

          {frame < 56 ? (
            <PixelSprite
              rows={ENEMY_SHIP}
              size={interpolate(frame, [10, 56], [11, 26], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              x={interpolate(frame, [10, 56], [1330, 1240], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              y={interpolate(frame, [10, 56], [320, 480], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
            />
          ) : null}

          {frame >= 17 && frame <= 29 ? (
            <rect
              x={696}
              y={interpolate(frame, [17, 29], [800, 470], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              width={12}
              height={70}
              fill={PALETTE.yellow}
            />
          ) : null}

          {frame >= 44 && frame <= 55 ? (
            <rect
              x={1236}
              y={interpolate(frame, [44, 55], [800, 480], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}
              width={12}
              height={70}
              fill={PALETTE.yellow}
            />
          ) : null}

          <PixelBurst
            x={700}
            y={470}
            seed={11}
            progress={interpolate(frame, [30, 52], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          />
          <PixelBurst
            x={1240}
            y={480}
            seed={77}
            progress={interpolate(frame, [56, 78], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
            scale={1.15}
          />

          <PixelSprite
            rows={PLAYER_SHIP}
            size={22}
            x={playerX}
            y={interpolate(frame, [0, 12], [1080, 880], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            })}
          />
        </svg>
      </Interactive.Div>

      <Interactive.Div
        name="Line one"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 100,
          textAlign: "center",
          color: "#3fd0ff",
          fontSize: 96,
          textShadow: "5px 0 0 rgba(255,59,48,0.6), -5px 0 0 rgba(255,210,30,0.6)",
          opacity: interpolate(frame, [4, 7], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [4, 16], [1.25, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        FIND SOLARIS
      </Interactive.Div>

      <Interactive.Div
        name="Line two"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 220,
          textAlign: "center",
          color: "#3ee66b",
          fontSize: 78,
          textShadow: "4px 0 0 rgba(255,59,48,0.5), -4px 0 0 rgba(63,208,255,0.5)",
          opacity: interpolate(frame, [18, 21], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [18, 30], [1.25, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        SAVE THE COLONY
      </Interactive.Div>
    </AbsoluteFill>
  );
};
