import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import {
  PRICES,
  VOLUMES,
  pointAt,
  priceToY,
  smoothPoints,
  toPath,
  yToPrice,
} from "./curve";

const { fontFamily } = loadFont();

const LEFT = 120;
const RIGHT = 1720;
const TOP = 300;
const BOTTOM = 800;
const VOLUME_BASE = 960;
const VOLUME_HEIGHT = 120;

const rawPoints = PRICES.map((price, i) => ({
  x: LEFT + (i / (PRICES.length - 1)) * (RIGHT - LEFT),
  y: priceToY(price, TOP, BOTTOM),
}));
const curve = smoothPoints(rawPoints);
const gridLevels = [0, 0.25, 0.5, 0.75, 1];

export const StockChart: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Drives the line, the area fill, the leading dot and the price readout.
  const progress = interpolate(frame, [0.4 * fps, 8.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.15, 1),
  });

  const head = pointAt(curve, progress);
  const drawn = curve.slice(
    0,
    Math.max(1, Math.ceil(progress * (curve.length - 1))),
  );
  const linePath = toPath([...drawn, head]);
  const areaPath = `${linePath} L${head.x.toFixed(2)} ${BOTTOM} L${LEFT} ${BOTTOM} Z`;

  const price = yToPrice(head.y, TOP, BOTTOM);
  const changePct = (price / PRICES[0] - 1) * 100;
  const pulse = (frame % (1.5 * fps)) / (1.5 * fps);

  return (
    <AbsoluteFill
      name="Scene"
      style={{
        backgroundColor: "#04120c",
        fontFamily,
        overflow: "hidden",
      }}
    >
      <Interactive.Div
        name="Camera"
        style={{
          position: "absolute",
          inset: 0,
          transformOrigin: "50% 60%",
          scale: interpolate(frame, [0, durationInFrames - 1], [1, 1.06], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
            output: "perceptual-scale",
          }),
        }}
      >
        <Interactive.Div
          name="Green glow"
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(90% 70% at 78% 78%, rgba(34,232,139,0.28) 0%, rgba(4,18,12,0) 65%)",
            opacity: interpolate(frame, [0, 1.5 * fps], [0, 1], {
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
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22e88b" stopOpacity="0.5" />
              <stop offset="55%" stopColor="#22e88b" stopOpacity="0.14" />
              <stop offset="100%" stopColor="#22e88b" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="lineStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#12a86a" />
              <stop offset="100%" stopColor="#5cffb0" />
            </linearGradient>
            <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="14" />
            </filter>
            <filter id="dotGlow" x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur stdDeviation="18" />
            </filter>
          </defs>

          {gridLevels.map((level, i) => {
            const y = TOP + level * (BOTTOM - TOP);
            const reveal = interpolate(
              frame,
              [0.2 * fps + i * 3, 1.2 * fps + i * 3],
              [0, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            );
            return (
              <g key={level} opacity={reveal}>
                <line
                  x1={LEFT}
                  y1={y}
                  x2={LEFT + reveal * (RIGHT - LEFT)}
                  y2={y}
                  stroke="rgba(120,255,190,0.12)"
                  strokeWidth={2}
                />
                <text
                  x={RIGHT + 34}
                  y={y + 11}
                  fill="rgba(190,255,225,0.4)"
                  fontSize={30}
                  fontWeight={500}
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {Math.round(yToPrice(y, TOP, BOTTOM))}
                </text>
              </g>
            );
          })}

          {VOLUMES.map((volume, i) => {
            const x = LEFT + (i / (VOLUMES.length - 1)) * (RIGHT - LEFT);
            const local = Math.min(
              1,
              Math.max(0, progress * (VOLUMES.length - 1) - i + 1),
            );
            const height = volume * VOLUME_HEIGHT * local;
            return (
              <rect
                key={i}
                x={x - 20}
                y={VOLUME_BASE - height}
                width={40}
                height={height}
                rx={6}
                fill="#22e88b"
                opacity={0.16 + local * 0.16}
              />
            );
          })}

          <path d={areaPath} fill="url(#areaFill)" />
          <path
            d={linePath}
            fill="none"
            stroke="#22e88b"
            strokeWidth={16}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.55}
            filter="url(#lineGlow)"
          />
          <path
            d={linePath}
            fill="none"
            stroke="url(#lineStroke)"
            strokeWidth={7}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          <line
            x1={head.x}
            y1={head.y}
            x2={head.x}
            y2={BOTTOM}
            stroke="rgba(92,255,176,0.28)"
            strokeWidth={2}
            strokeDasharray="10 12"
          />
          <circle
            cx={head.x}
            cy={head.y}
            r={18 + pulse * 52}
            fill="none"
            stroke="#5cffb0"
            strokeWidth={4}
            opacity={0.5 - pulse * 0.5}
          />
          <circle
            cx={head.x}
            cy={head.y}
            r={26}
            fill="#5cffb0"
            opacity={0.45}
            filter="url(#dotGlow)"
          />
          <circle cx={head.x} cy={head.y} r={13} fill="#eafff4" />
        </svg>

        <Interactive.Div
          name="Ticker"
          style={{
            position: "absolute",
            left: 120,
            top: 118,
            color: "rgba(190,255,225,0.6)",
            fontSize: 40,
            fontWeight: 600,
            letterSpacing: 14,
            opacity: interpolate(frame, [0.3 * fps, 1.3 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            translate: interpolate(
              frame,
              [0.3 * fps, 1.3 * fps],
              ["0px 24px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          ACME · NASDAQ
        </Interactive.Div>

        <Interactive.Div
          name="Price"
          style={{
            position: "absolute",
            left: 120,
            top: 168,
            color: "#ffffff",
            fontSize: 148,
            fontWeight: 700,
            letterSpacing: -4,
            fontVariantNumeric: "tabular-nums",
            opacity: interpolate(frame, [0.5 * fps, 1.5 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            translate: interpolate(
              frame,
              [0.5 * fps, 1.5 * fps],
              ["0px 32px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          ${price.toFixed(2)}
        </Interactive.Div>

        <Interactive.Div
          name="Change pill"
          style={{
            position: "absolute",
            left: 124,
            top: 356,
            display: "inline-flex",
            alignItems: "center",
            padding: "14px 34px",
            borderRadius: 999,
            backgroundColor: "rgba(34,232,139,0.14)",
            border: "2px solid rgba(34,232,139,0.4)",
            color: "#5cffb0",
            fontSize: 52,
            fontWeight: 600,
            fontVariantNumeric: "tabular-nums",
            opacity: interpolate(frame, [0.8 * fps, 1.8 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            scale: interpolate(frame, [0.8 * fps, 1.8 * fps], [0.85, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.spring({ damping: 200 }),
              output: "perceptual-scale",
            }),
          }}
        >
          ▲ +{changePct.toFixed(1)}%
        </Interactive.Div>

        <Interactive.Div
          name="Live badge"
          style={{
            position: "absolute",
            right: 120,
            top: 128,
            display: "inline-flex",
            alignItems: "center",
            gap: 18,
            color: "rgba(190,255,225,0.65)",
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: 8,
            opacity: interpolate(frame, [1 * fps, 2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <Interactive.Div
            name="Live dot"
            style={{
              width: 20,
              height: 20,
              borderRadius: 999,
              backgroundColor: "#5cffb0",
              opacity: interpolate(frame % 45, [0, 22, 45], [1, 0.25, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.4, 0, 0.6, 1),
              }),
            }}
          />
          LIVE
        </Interactive.Div>

        <Interactive.Div
          name="Vignette"
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(75% 75% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)",
          }}
        />
      </Interactive.Div>
    </AbsoluteFill>
  );
};
