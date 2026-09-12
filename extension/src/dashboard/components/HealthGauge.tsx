import { INK, MUTED } from "../../lib/theme";
import { scoreTier, TIER_COLORS, TIER_HEX, type Tier } from "../severity";

const SIZE = { width: 280, height: 150, cx: 140, cy: 128, radius: 96, stroke: 16 };

const ZONES: { from: number; to: number; tier: Tier }[] = [
  { from: 0, to: 50, tier: "critical" },
  { from: 50, to: 80, tier: "fair" },
  { from: 80, to: 100, tier: "good" },
];

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const angleRad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) };
}

function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end = polarToCartesian(cx, cy, r, endAngle);
  const largeArcFlag = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`;
}

/** Maps a 0-100 score onto the -90deg (left) .. 90deg (right) sweep of the
 * semicircular gauge, passing through 0deg (top) at the midpoint. */
function scoreToAngle(score: number) {
  return -90 + (Math.max(0, Math.min(100, score)) / 100) * 180;
}

export function HealthGauge({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const tier = scoreTier(clamped);
  const colors = TIER_COLORS[tier];
  const needleAngle = scoreToAngle(clamped);
  const needleTip = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius - SIZE.stroke / 2 - 6, needleAngle);

  return (
    <div className="flex w-full max-w-[260px] flex-col items-center">
      <svg viewBox={`0 0 ${SIZE.width} ${SIZE.height}`} className="w-full" role="img" aria-label={`Health score ${Math.round(clamped)} out of 100`}>
        <defs>
          <filter id="gauge-needle-shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor={INK} floodOpacity="0.35" />
          </filter>
        </defs>

        {ZONES.map((zone) => (
          <path
            key={zone.tier}
            d={arcPath(SIZE.cx, SIZE.cy, SIZE.radius, scoreToAngle(zone.from), scoreToAngle(zone.to))}
            fill="none"
            stroke={TIER_HEX[zone.tier]}
            strokeWidth={SIZE.stroke}
            strokeLinecap="butt"
          />
        ))}

        {[0, 50, 100].map((tick) => {
          const angle = scoreToAngle(tick);
          const inner = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius - SIZE.stroke / 2 - 3, angle);
          const outer = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius + SIZE.stroke / 2 + 3, angle);
          const labelPos = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius + SIZE.stroke / 2 + 13, angle);
          return (
            <g key={tick}>
              <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke="#FFFFFF" strokeWidth={1.5} opacity={0.9} />
              <text x={labelPos.x} y={labelPos.y} textAnchor="middle" dominantBaseline="middle" fill={MUTED} fontSize={10} fontWeight={700}>
                {tick}
              </text>
            </g>
          );
        })}

        <g filter="url(#gauge-needle-shadow)">
          <line x1={SIZE.cx} y1={SIZE.cy} x2={needleTip.x} y2={needleTip.y} stroke={INK} strokeWidth={3} strokeLinecap="round" />
          <circle cx={SIZE.cx} cy={SIZE.cy} r={7} fill={INK} />
          <circle cx={SIZE.cx} cy={SIZE.cy} r={2.5} fill="#FFFFFF" />
        </g>

        <text x={SIZE.cx} y={SIZE.cy - 34} textAnchor="middle" fontSize={44} fontWeight={800} fill={TIER_HEX[tier]}>
          {Math.round(clamped)}
        </text>
      </svg>

      <p className={`mt-2 text-sm font-extrabold tracking-wide uppercase ${colors.text}`}>{colors.verdict}</p>
      <p className="mt-1.5 max-w-[220px] text-center text-xs leading-relaxed text-muted">{colors.subtext}</p>
    </div>
  );
}
