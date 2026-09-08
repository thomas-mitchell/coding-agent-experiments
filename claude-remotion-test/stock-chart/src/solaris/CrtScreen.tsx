import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";

// Wraps a scene in the look of a 1986 CRT: scanlines, phosphor bloom, vignette
// and a faint rolling refresh bar.
export const CrtScreen: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="CRT" style={{ backgroundColor: "#000000" }}>
      {children}

      <Interactive.Div
        name="Roll bar"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          height: 260,
          background:
            "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.05) 50%, rgba(255,255,255,0) 100%)",
          translate: interpolate(frame % 90, [0, 90], ["0px -300px", "0px 1180px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
        }}
      />

      <Interactive.Div
        name="Scanlines"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "repeating-linear-gradient(180deg, rgba(0,0,0,0.45) 0px, rgba(0,0,0,0.45) 3px, rgba(0,0,0,0) 3px, rgba(0,0,0,0) 6px)",
          mixBlendMode: "multiply",
        }}
      />

      <Interactive.Div
        name="Vignette"
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(72% 72% at 50% 50%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.85) 100%)",
        }}
      />

      <Interactive.Div
        name="Flicker"
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "#ffffff",
          opacity: interpolate(frame % 7, [0, 3, 7], [0.02, 0.045, 0.02], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.linear,
          }),
        }}
      />
    </AbsoluteFill>
  );
};
