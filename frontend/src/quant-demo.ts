/** Seeded demo verisi ve kucuk istemci yardimcilari (Quant Lab). */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const gauss = (r: () => number) => (r() + r() + r() + r() - 2) / 1.2;

export function demoFeatureMatrix(n = 240, seed = 42) {
  const r = mulberry32(seed);
  const target = Array.from({ length: n }, () => gauss(r));
  const f0 = target.map((v) => v * 0.6 + gauss(r) * 0.8);
  const f1 = f0.map((v) => v + gauss(r) * 0.05); // f0'un neredeyse kopyasi
  const features: Record<string, number[]> = {
    momentum_20: f0,
    momentum_20_copy: f1,
    reversal_5: target.map((v) => -v * 0.3 + gauss(r)),
    volatility_14: Array.from({ length: n }, () => Math.abs(gauss(r))),
    noise_a: Array.from({ length: n }, () => gauss(r)),
    noise_b: Array.from({ length: n }, () => gauss(r)),
  };
  return { features, target };
}

export function demoCalibration(n = 400, seed = 7) {
  const r = mulberry32(seed);
  const y_prob = Array.from({ length: n }, () => 0.05 + r() * 0.9);
  const y_true = y_prob.map((p) => (r() < p * 0.7 + 0.15 ? 1 : 0));
  return { y_true, y_prob };
}

export function demoQuantile(n = 200, seed = 13) {
  const r = mulberry32(seed);
  const X: number[][] = Array.from({ length: n }, () => [gauss(r), gauss(r), gauss(r)]);
  const y = X.map((row) => row[0] * 2 - row[1] + gauss(r) * 0.5);
  return { X, y };
}

export function demoStress(n = 300, seed = 11) {
  const r = mulberry32(seed);
  const predictions = Array.from({ length: n }, () => gauss(r));
  const actuals = predictions.map((p) => p * 0.0004 + gauss(r) * 0.001);
  return { predictions, actuals };
}

export function pearson(a: number[], b: number[]) {
  const n = Math.min(a.length, b.length);
  if (n < 3) return 0;
  const ma = a.reduce((s, v) => s + v, 0) / n, mb = b.reduce((s, v) => s + v, 0) / n;
  let cov = 0, va = 0, vb = 0;
  for (let i = 0; i < n; i++) { cov += (a[i] - ma) * (b[i] - mb); va += (a[i] - ma) ** 2; vb += (b[i] - mb) ** 2; }
  return va > 1e-12 && vb > 1e-12 ? cov / Math.sqrt(va * vb) : 0;
}
