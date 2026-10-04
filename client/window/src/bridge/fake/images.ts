/* Pictures the fake app hands the window, the way the real one will: as data URLs made on this PC. */

const url = (svg: string) => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);

/** A captcha as KFintech would draw it: skewed characters over noise. */
export function captcha(text: string): string {
  const chars = [...text].map((c, i) =>
    `<text x="${28 + i * 34}" y="${52 + (i % 2 ? -6 : 5)}" transform="rotate(${(i % 3 - 1) * 12} ${28 + i * 34} 46)">${c}</text>`).join('');
  return url(`<svg xmlns="http://www.w3.org/2000/svg" width="220" height="80" viewBox="0 0 220 80">
    <rect width="220" height="80" fill="#eef1f5"/>
    <path d="M0 50 C40 20 80 70 120 40 S190 20 220 55" stroke="#9aa6ba" stroke-width="2" fill="none"/>
    <path d="M0 30 C50 60 110 10 160 50 S210 30 220 30" stroke="#b9c2d0" stroke-width="1.5" fill="none"/>
    <g font-family="Georgia, serif" font-size="34" font-style="italic" fill="#3b4a66">${chars}</g></svg>`);
}

const INK = '<path d="M8 48c10-30 22-38 26-30s-10 34-4 36 14-30 20-30-2 26 4 26 10-18 16-18-2 16 4 16 8-12 14-12"/><path d="M104 40c6-14 14-22 18-18s-8 26 0 26 16-28 24-28-4 22 4 22 10-10 18-12 16 2 30-6"/><path d="M40 60c40-4 90-6 150-8"/>';

/** The cleaned signature: ink on transparent, turned by `turns` quarter turns (a sideways photo arrives turned). */
export function signature(turns = 0): string {
  const q = ((turns % 4) + 4) % 4, w = q % 2 ? 70 : 220, h = q % 2 ? 220 : 70;
  const t = [``, `translate(70 0) rotate(90)`, `translate(220 70) rotate(180)`, `translate(0 220) rotate(270)`][q];
  return url(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <g transform="${t}" fill="none" stroke="#1b2a5a" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${INK}</g></svg>`);
}
