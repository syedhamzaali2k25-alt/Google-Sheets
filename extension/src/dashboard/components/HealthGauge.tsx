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
  const needleTip = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius - SIZE.stroke / 2 - 4, needleAngle);

  return (
    <div className="flex w-full max-w-[260px] flex-col items-center">
      <svg viewBox={`0 0 ${SIZE.width} ${SIZE.height}`} className="w-full" role="img" aria-label={`Health score ${Math.round(clamped)} out of 100`}>
        {ZONES.map((zone) => (
          <path
            key={zone.tier}
            d={arcPath(SIZE.cx, SIZE.cy, SIZE.radius, scoreToAngle(zone.from), scoreToAngle(zone.to))}
            fill="none"
            stroke={TIER_HEX[zone.tier]}
            strokeWidth={SIZE.stroke}
          />
        ))}

        {[0, 50, 100].map((tick) => {
          const angle = scoreToAngle(tick);
          const inner = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius - SIZE.stroke / 2 - 3, angle);
          const outer = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius + SIZE.stroke / 2 + 3, angle);
          const labelPos = polarToCartesian(SIZE.cx, SIZE.cy, SIZE.radius + SIZE.stroke / 2 + 12, angle);
          return (
            <g key={tick}>
              <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke="#C7CCD6" strokeWidth={1.5} />
              <text x={labelPos.x} y={labelPos.y} textAnchor="middle" dominantBaseline="middle" fill="#8A93A6" fontSize={10} fontWeight={600}>
                {tick}
              </text>
            </g>
          );
        })}

        <line
          x1={SIZE.cx}
          y1={SIZE.cy}
          x2={needleTip.x}
          y2={needleTip.y}
          stroke="#1A2233"
          strokeWidth={3}
          strokeLinecap="round"
        />
        <circle cx={SIZE.cx} cy={SIZE.cy} r={6} fill="#1A2233" />

        <text x={SIZE.cx} y={SIZE.cy - 34} textAnchor="middle" fontSize={42} fontWeight={800} fill={TIER_HEX[tier]}>
          {Math.round(clamped)}
        </text>
      </svg>

      <p className={`mt-1 text-sm font-extrabold tracking-wide uppercase ${colors.text}`}>{colors.verdict}</p>
      <p className="mt-1 max-w-[220px] text-center text-xs text-[#8A93A6]">{colors.subtext}</p>
    </div>
  );
}
