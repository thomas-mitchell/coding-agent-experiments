import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/PressStart2P";
import { PALETTE } from "./pixels";

const { fontFamily } = loadFont();
const rays = Array.from({ length: 16 }, (_, i) => i);

export const LogoScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Logo" style={{ backgroundColor: "#0a0418", fontFamily }}>
      <Interactive.Div
        name="Sun glow"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(55% 55% at 50% 45%, rgba(255,159,46,0.55) 0%, rgba(120,20,90,0.35) 45%, rgba(0,0,0,0) 75%)",
        }}
      />

      <svg
        width="1920"
        height="1080"
        viewBox="0 0 1920 1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <g
          transform={`rotate(${interpolate(frame, [0, 81], [0, 26], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          })} 960 480)`}
        >
          {rays.map((i) => (
            <polygon
              key={i}
              points="960,480 2600,380 2600,580"
              fill={i % 2 === 0 ? PALETTE.orange : PALETTE.yellow}
              opacity={0.13}
              transform={`rotate(${i * 22.5} 960 480)`}
            />
          ))}
        </g>

        <circle cx={960} cy={1680} r={680} fill="#120a2e" />
        <circle
          cx={960}
          cy={1680}
          r={680}
          fill="none"
          stroke={PALETTE.cyan}
          strokeWidth={8}
          opacity={0.8}
        />
        <circle
          cx={960}
          cy={1680}
          r={646}
          fill="none"
          stroke={PALETTE.magenta}
          strokeWidth={4}
          opacity={0.5}
        />
      </svg>

      <Interactive.Div
        name="Wordmark"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 330,
          textAlign: "center",
          color: "#ffd21e",
          fontSize: 196,
          WebkitTextStroke: "9px #a3120b",
          paintOrder: "stroke fill",
          textShadow: "0 14px 0 #6d0a06, 0 0 60px rgba(255,159,46,0.85)",
          scale: interpolate(frame, [0, 9, 14], [3.2, 0.92, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
          opacity: interpolate(frame, [0, 2], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
        }}
      >
        SOLARIS
      </Interactive.Div>

      <Interactive.Div
        name="Platform"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 640,
          textAlign: "center",
          color: "#3fd0ff",
          fontSize: 56,
          letterSpacing: 8,
          textShadow: "0 0 26px rgba(63,208,255,0.8)",
          opacity: interpolate(frame, [18, 21], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
          scale: interpolate(frame, [18, 30], [1.18, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
        }}
      >
        FOR THE ATARI 2600
      </Interactive.Div>

      <Interactive.Div
        name="Kicker"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 790,
          textAlign: "center",
          color: "#3ee66b",
          fontSize: 38,
          letterSpacing: 5,
          opacity: interpolate(frame % 30, [0, 15, 30], [0.3, 1, 0.3], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.4, 0, 0.6, 1),
          }),
        }}
      >
        THE GALAXY IS WAITING
      </Interactive.Div>

      <Interactive.Div
        name="Disclaimer"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 926,
          textAlign: "center",
          color: "rgba(244,244,244,0.6)",
          fontSize: 20,
          letterSpacing: 4,
          opacity: interpolate(frame, [40, 50], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
        }}
      >
        FAN TRIBUTE · SOLARIS RELEASED 1986
      </Interactive.Div>

      <Interactive.Div
        name="Flash"
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "#ffffff",
          opacity: interpolate(frame, [0, 9], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.4, 0, 1, 1),
          }),
        }}
      />
    </AbsoluteFill>
  );
};
