export type Point = { x: number; y: number };

// Closing prices of a fictional ticker, trending up with realistic pullbacks.
export const PRICES = [
  104, 111, 107, 125, 137, 129, 151, 167, 160, 183, 198, 189, 213, 235, 227,
  257, 280, 269, 301, 329, 317, 355, 391, 428,
];

// Relative trading volume per data point (0-1), used for the bars under the chart.
export const VOLUMES = [
  0.32, 0.41, 0.28, 0.55, 0.47, 0.3, 0.62, 0.58, 0.35, 0.66, 0.71, 0.42, 0.6,
  0.78, 0.44, 0.73, 0.86, 0.5, 0.79, 0.92, 0.55, 0.88, 0.97, 1,
];

export const minPrice = Math.min(...PRICES);
export const maxPrice = Math.max(...PRICES);

export const priceToY = (
  price: number,
  top: number,
  bottom: number,
): number => {
  // 12% headroom above and below so the line never touches the chart edges.
  const span = (maxPrice - minPrice) * 1.12;
  const base = minPrice - (maxPrice - minPrice) * 0.06;
  return bottom - ((price - base) / span) * (bottom - top);
};

const catmullRom = (
  p0: number,
  p1: number,
  p2: number,
  p3: number,
  t: number,
): number => {
  const t2 = t * t;
  const t3 = t2 * t;
  return (
    0.5 *
    (2 * p1 +
      (-p0 + p2) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
  );
};

// Turns the raw data points into a dense, smoothly interpolated polyline.
export const smoothPoints = (points: Point[], perSegment = 24): Point[] => {
  const out: Point[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    for (let s = 0; s < perSegment; s++) {
      const t = s / perSegment;
      out.push({
        x: catmullRom(p0.x, p1.x, p2.x, p3.x, t),
        y: catmullRom(p0.y, p1.y, p2.y, p3.y, t),
      });
    }
  }
  out.push(points[points.length - 1]);
  return out;
};

export const toPath = (points: Point[]): string =>
  points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(" ");

// Position along the dense polyline at `progress` (0-1) of its horizontal span.
export const pointAt = (points: Point[], progress: number): Point => {
  const raw = progress * (points.length - 1);
  const i = Math.min(points.length - 2, Math.max(0, Math.floor(raw)));
  const t = raw - i;
  return {
    x: points[i].x + (points[i + 1].x - points[i].x) * t,
    y: points[i].y + (points[i + 1].y - points[i].y) * t,
  };
};

export const yToPrice = (y: number, top: number, bottom: number): number => {
  const span = (maxPrice - minPrice) * 1.12;
  const base = minPrice - (maxPrice - minPrice) * 0.06;
  return base + ((bottom - y) / (bottom - top)) * span;
};
