// Chunky pixel-art helpers so every sprite reads like 1986 hardware.

export const PALETTE = {
  black: "#000000",
  deepBlue: "#101a4c",
  cyan: "#3fd0ff",
  green: "#3ee66b",
  yellow: "#ffd21e",
  orange: "#ff9f2e",
  red: "#ff3b30",
  magenta: "#ff5cd0",
  white: "#f4f4f4",
};

// Player fighter, seen from behind. "." is transparent.
export const PLAYER_SHIP = [
  "....y....",
  "....y....",
  "...ooo...",
  "...ooo...",
  "..ooooo..",
  ".ooccooo.",
  "ooc.o.coo",
  "oo..y..oo",
  "r.......r",
];

// Zylon raider, nose pointing down at the player.
export const ENEMY_SHIP = [
  "m.......m",
  "mm.....mm",
  ".mmm.mmm.",
  "..mmrmm..",
  "...mrm...",
  "....r....",
];

// Fuel tanker / colony transport seen on the sector map.
export const COLONY = [
  ".ggg.",
  "gcccg",
  "gcycg",
  "gcccg",
  ".ggg.",
];

const CHAR_TO_COLOR: Record<string, string> = {
  y: PALETTE.yellow,
  o: PALETTE.orange,
  c: PALETTE.cyan,
  r: PALETTE.red,
  m: PALETTE.magenta,
  g: PALETTE.green,
  w: PALETTE.white,
};

export const PixelSprite: React.FC<{
  rows: string[];
  size: number;
  x: number;
  y: number;
  opacity?: number;
}> = ({ rows, size, x, y, opacity = 1 }) => {
  const width = rows[0].length * size;
  const height = rows.length * size;
  return (
    <g
      transform={`translate(${x - width / 2} ${y - height / 2})`}
      opacity={opacity}
    >
      {rows.map((row, ry) =>
        row.split("").map((char, rx) => {
          const fill = CHAR_TO_COLOR[char];
          if (!fill) {
            return null;
          }
          return (
            <rect
              key={`${rx}-${ry}`}
              x={rx * size}
              y={ry * size}
              width={size}
              height={size}
              fill={fill}
            />
          );
        }),
      )}
    </g>
  );
};

// Deterministic PRNG so the starfield is identical on every render pass.
const mulberry32 = (seed: number) => {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

export type Star = { angle: number; offset: number; speed: number };

export const makeStars = (count: number, seed: number): Star[] => {
  const random = mulberry32(seed);
  const stars: Star[] = [];
  for (let i = 0; i < count; i++) {
    stars.push({
      angle: random() * Math.PI * 2,
      offset: random(),
      speed: 0.5 + random() * 0.9,
    });
  }
  return stars;
};

const STAR_COLORS = [
  PALETTE.white,
  PALETTE.cyan,
  PALETTE.yellow,
  PALETTE.white,
  PALETTE.orange,
];

// Stars stream outward from the vanishing point; radius drives size and length.
export const Starfield: React.FC<{
  stars: Star[];
  time: number;
  streak: number;
  centerX?: number;
  centerY?: number;
}> = ({ stars, time, streak, centerX = 960, centerY = 540 }) => (
  <g>
    {stars.map((star, i) => {
      const raw = (star.offset + time * star.speed) % 1;
      const radius = raw * raw * 1250;
      const prev = Math.max(0, raw - streak);
      const prevRadius = prev * prev * 1250;
      const size = Math.max(3, Math.round((3 + raw * 14) / 3) * 3);
      const x1 = centerX + Math.cos(star.angle) * prevRadius;
      const y1 = centerY + Math.sin(star.angle) * prevRadius * 0.62;
      const x2 = centerX + Math.cos(star.angle) * radius;
      const y2 = centerY + Math.sin(star.angle) * radius * 0.62;
      return (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={STAR_COLORS[i % STAR_COLORS.length]}
          strokeWidth={size}
          strokeLinecap="butt"
          opacity={0.25 + raw * 0.75}
        />
      );
    })}
  </g>
);

// Expanding ring of pixel chunks, used for ship explosions.
export const PixelBurst: React.FC<{
  x: number;
  y: number;
  progress: number;
  seed: number;
  scale?: number;
}> = ({ x, y, progress, seed, scale = 1 }) => {
  if (progress <= 0 || progress >= 1) {
    return null;
  }
  const random = mulberry32(seed);
  const chunks = Array.from({ length: 26 }, () => ({
    angle: random() * Math.PI * 2,
    distance: 0.4 + random() * 0.6,
    size: (12 + Math.floor(random() * 4) * 9) * scale,
  }));
  const colors = [PALETTE.white, PALETTE.yellow, PALETTE.orange, PALETTE.red];
  return (
    <g opacity={1 - progress * progress}>
      {chunks.map((chunk, i) => (
        <rect
          key={i}
          x={x + Math.cos(chunk.angle) * chunk.distance * progress * 320 * scale}
          y={y + Math.sin(chunk.angle) * chunk.distance * progress * 320 * scale}
          width={chunk.size}
          height={chunk.size}
          fill={colors[i % colors.length]}
        />
      ))}
    </g>
  );
};
