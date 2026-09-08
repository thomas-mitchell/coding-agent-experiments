import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/PressStart2P";
import { COLONY, ENEMY_SHIP, PALETTE, PixelSprite } from "./pixels";

const { fontFamily } = loadFont();

const GRID_LEFT = 240;
const GRID_TOP = 250;
const CELL_W = 120;
const CELL_H = 80;
const COLS = 12;
const ROWS = 6;

// Hand-placed sector contents: e = Zylon fleet, c = colony, f = fuel.
const SECTORS = [
  "..e....f..e.",
  ".f..e.....c.",
  "e....c..e...",
  "..c...f...e.",
  ".e..f...c...",
  "....e..e..f.",
];

export const MapScene: React.FC = () => {
  const frame = useCurrentFrame();

  const scanX = interpolate(frame, [2, 50], [GRID_LEFT, GRID_LEFT + COLS * CELL_W], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.linear,
  });

  return (
    <AbsoluteFill name="Map" style={{ backgroundColor: "#03060f", fontFamily }}>
      <Interactive.Div
        name="Scanner glow"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(65% 55% at 50% 42%, rgba(16,58,120,0.65) 0%, rgba(0,0,0,0) 72%)",
        }}
      />

      <svg
        width="1920"
        height="1080"
        viewBox="0 0 1920 1080"
        style={{ position: "absolute", inset: 0 }}
      >
        {Array.from({ length: COLS + 1 }, (_, i) => (
          <line
            key={`v${i}`}
            x1={GRID_LEFT + i * CELL_W}
            y1={GRID_TOP}
            x2={GRID_LEFT + i * CELL_W}
            y2={GRID_TOP + ROWS * CELL_H}
            stroke="rgba(63,208,255,0.22)"
            strokeWidth={2}
          />
        ))}
        {Array.from({ length: ROWS + 1 }, (_, i) => (
          <line
            key={`h${i}`}
            x1={GRID_LEFT}
            y1={GRID_TOP + i * CELL_H}
            x2={GRID_LEFT + COLS * CELL_W}
            y2={GRID_TOP + i * CELL_H}
            stroke="rgba(63,208,255,0.22)"
            strokeWidth={2}
          />
        ))}

        {SECTORS.map((row, ry) =>
          row.split("").map((cell, rx) => {
            const cx = GRID_LEFT + rx * CELL_W + CELL_W / 2;
            const cy = GRID_TOP + ry * CELL_H + CELL_H / 2;
            if (cell === "." || scanX < cx) {
              return null;
            }
            if (cell === "e") {
              return (
                <PixelSprite
                  key={`${rx}-${ry}`}
                  rows={ENEMY_SHIP}
                  size={6}
                  x={cx}
                  y={cy}
                  opacity={frame % 14 < 7 ? 1 : 0.35}
                />
              );
            }
            if (cell === "c") {
              return (
                <PixelSprite
                  key={`${rx}-${ry}`}
                  rows={COLONY}
                  size={9}
                  x={cx}
                  y={cy}
                />
              );
            }
            return (
              <rect
                key={`${rx}-${ry}`}
                x={cx - 15}
                y={cy - 15}
                width={30}
                height={30}
                fill={PALETTE.yellow}
                opacity={0.9}
              />
            );
          }),
        )}

        <rect
          x={scanX - 6}
          y={GRID_TOP}
          width={12}
          height={ROWS * CELL_H}
          fill={PALETTE.cyan}
          opacity={0.85}
        />
        <rect
          x={scanX - 60}
          y={GRID_TOP}
          width={60}
          height={ROWS * CELL_H}
          fill={PALETTE.cyan}
          opacity={0.15}
        />

        <g
          transform={`translate(${interpolate(frame, [20, 70], [420, 1400], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.65, 0, 0.35, 1),
          })} ${interpolate(frame, [20, 70], [530, 330], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.65, 0, 0.35, 1),
          })})`}
        >
          <rect x={-72} y={-56} width={34} height={9} fill={PALETTE.green} />
          <rect x={-72} y={-56} width={9} height={34} fill={PALETTE.green} />
          <rect x={38} y={-56} width={34} height={9} fill={PALETTE.green} />
          <rect x={63} y={-56} width={9} height={34} fill={PALETTE.green} />
          <rect x={-72} y={47} width={34} height={9} fill={PALETTE.green} />
          <rect x={-72} y={22} width={9} height={34} fill={PALETTE.green} />
          <rect x={38} y={47} width={34} height={9} fill={PALETTE.green} />
          <rect x={63} y={22} width={9} height={34} fill={PALETTE.green} />
        </g>
      </svg>

      <Interactive.Div
        name="Scanner label"
        style={{
          position: "absolute",
          left: 240,
          top: 150,
          color: "#3fd0ff",
          fontSize: 34,
          letterSpacing: 6,
          opacity: interpolate(frame % 30, [0, 15, 30], [0.55, 1, 0.55], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.4, 0, 0.6, 1),
          }),
        }}
      >
        GALACTIC SCANNER ONLINE
      </Interactive.Div>

      <Interactive.Div
        name="Headline"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 810,
          textAlign: "center",
          color: "#ffd21e",
          fontSize: 96,
          textShadow: "5px 0 0 rgba(255,59,48,0.6), -5px 0 0 rgba(63,208,255,0.6)",
          opacity: interpolate(frame, [12, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [12, 24], [1.25, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        16 QUADRANTS
      </Interactive.Div>

      <Interactive.Div
        name="Subhead"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 930,
          textAlign: "center",
          color: "#3ee66b",
          fontSize: 40,
          letterSpacing: 4,
          opacity: interpolate(frame, [26, 29], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
        }}
      >
        48 SECTORS OF WAR
      </Interactive.Div>
    </AbsoluteFill>
  );
};
