/**
 * Real-data panels for the Agent Analytics tab, fed by agent_profiles_*.json
 * (per-agent dossier) and agent_aggregates.json (population dashboards) —
 * replacing the previous fabricated getFake* placeholders.
 */
import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip,
} from 'recharts';

// Design tokens mirrored from the main dashboard (src/index.css)
const LBL = 'rgba(255,255,255,0.32)';
const TXT2 = 'rgba(255,255,255,0.55)';
const TXT = 'rgba(255,255,255,0.86)';
const BDR = 'rgba(255,255,255,0.08)';
const BDR2 = 'rgba(255,255,255,0.14)';
// Liquid-glass tokens mirrored from the dashboard KPI cards (--glass* in app/src/index.css)
const CARD = 'rgba(28,28,30,0.55)';            // --glass fill
const GLASS_BDR = 'rgba(255,255,255,0.10)';    // --glass-bdr
const GLASS_SHADOW = '0 8px 30px rgba(0,0,0,0.55), 0 2px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.12)'; // --glass-shadow + --glass-hi
const GLASS_BLUR = 'blur(28px) saturate(1.7)'; // --glass-blur
const ACCENT = '#0A84FF';   // sys-blue — data accent
const TITLE = `'Syne', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif`;

// Ekman emotion palette (Apple system colors), order:
// [ANGER, CONTEMPT, DISGUST, ENJOYMENT, FEAR, SADNESS, SURPRISE]
const EKMAN_RGB = ['#FF453A', '#BF5AF2', '#FFD60A', '#30D158', '#FF9F0A', '#0A84FF', '#64D2FF'];

const ACTIVITY_COLORS: Record<string, string> = {
  work: '#60a5fa', education: '#a78bfa', grocery: '#34d399', shopping: '#fbbf24',
  leisure_indoor: '#f472b6', leisure_outdoor: '#4ade80', healthcare: '#f87171',
  civic: '#22d3ee', escort: '#fb923c', home: '#475569',
};
const MODE_COLORS: Record<string, string> = { car: '#f87171', bus: '#fbbf24', walk: '#34d399' };

const cap = (s?: string) => (s ? s.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()) : '—');
const hhmm = (min: number) => `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(Math.floor(min % 60)).padStart(2, '0')}`;

// ── small building blocks ───────────────────────────────────────────────────
const Section = ({ title, children, right }: any) => (
  <div style={{ borderTop: `0.5px solid ${BDR}`, paddingTop: 12, marginTop: 12 }}>
    <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 8 }}>
      <div style={{ fontFamily: TITLE, fontSize: 11, fontWeight: 500, color: TXT2 }}>{title}</div>
      {right && <div style={{ marginLeft: 'auto', fontSize: 10, color: LBL }}>{right}</div>}
    </div>
    {children}
  </div>
);

const Bar01 = ({ label, value, color = ACCENT, fmt }: { label: string; value: number | null; color?: string; fmt?: (v: number) => string }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
    <span style={{ fontSize: 10, color: LBL, width: 96, flexShrink: 0, textTransform: 'capitalize' }}>{label}</span>
    <div style={{ flex: 1, height: 5, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <div style={{ height: '100%', borderRadius: 999, background: color, width: `${Math.round(((value ?? 0)) * 100)}%` }} />
    </div>
    <span style={{ fontSize: 10, color: TXT, width: 32, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
      {value == null ? '—' : (fmt ? fmt(value) : value.toFixed(2))}
    </span>
  </div>
);

const Chip = ({ children, color = '#374151' }: any) => (
  <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: color, color: '#e5e7eb', whiteSpace: 'nowrap' }}>{children}</span>
);

const Row = ({ k, v, c }: { k: string; v: any; c?: string }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '2px 0' }}>
    <span style={{ color: LBL, letterSpacing: '0.03em' }}>{k}</span>
    <span style={{ color: c || TXT, textAlign: 'right', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{v ?? '—'}</span>
  </div>
);

// ── derive a grounded emotion explanation from the profile ──────────────────
export function emotionDrivers(p: any): { driver: string; weight: number }[] {
  if (!p || p.minor) return [];
  const big5 = p.big5 || [], econ = p.econ || [], soc = p.soc || [];
  const neuroticism = big5[4] ?? 0.5, extraversion = big5[2] ?? 0.5;
  const finStress = econ[0] ?? 0.5, jobSec = econ[3] ?? 0.5, bridging = soc[1] ?? 0.5;
  const drivers = [
    { driver: 'Neuroticism', weight: neuroticism },
    { driver: 'Financial stress', weight: finStress },
    { driver: 'Job insecurity', weight: 1 - jobSec },
    { driver: 'Extraversion', weight: extraversion },
    { driver: 'Social bridging', weight: bridging },
  ];
  return drivers.sort((a, b) => b.weight - a.weight);
}

const EKMAN = ['ANGER', 'CONTEMPT', 'DISGUST', 'ENJOYMENT', 'FEAR', 'SADNESS', 'SURPRISE'];

// Placeholder Ekman mood vector for the 3D emotion bubble: dominant = the agent's
// current emotion, lightly tinted by profile drivers (neuroticism, financial
// stress). Frontend placeholder until real emotion dynamics exist.
export function placeholderMoodVector(profile: any, emotion: string | null): number[] {
  const v = EKMAN.map(() => 0.06);
  const di = EKMAN.indexOf((emotion || 'ENJOYMENT').toUpperCase());
  if (di >= 0) v[di] = 0.7;
  if (profile && !profile.minor) {
    const neuro = profile.big5?.[4] ?? 0.5, fin = profile.econ?.[0] ?? 0.5;
    v[0] += neuro * 0.15;                       // anger
    v[4] += (neuro * 0.5 + fin * 0.5) * 0.2;    // fear
    v[5] += fin * 0.12;                          // sadness
  }
  const s = v.reduce((a, b) => a + b, 0) || 1;
  return v.map(x => x / s);
}

// ── Big Five personality ─────────────────────────────────────────────────────
// Bipolar OCEAN traits as labeled bars — far easier to read exact scores than a
// radar. Each bar carries the pole word it leans toward and a faint tick at 50%
// (the population midpoint) so a score reads as "above / below average" at a glance.
// Aligned with the scenario palette (src/utils/chartUtils.js OVERLAY_SCENARIOS):
// Openness↔Continuity blue, Conscientiousness↔Degrowth green, Extraversion↔Density
// yellow, Neuroticism↔Overgrowth red, Agreeableness in the same deep shade, purple.
const BIG5_TRAITS = [
  { name: 'Openness',          color: '#294daf', lo: 'Consistent',  hi: 'Curious' },
  { name: 'Conscientiousness', color: '#076f37', lo: 'Spontaneous', hi: 'Organized' },
  { name: 'Extraversion',      color: '#eab308', lo: 'Reserved',    hi: 'Outgoing' },
  { name: 'Agreeableness',     color: '#6b21a8', lo: 'Frank',       hi: 'Warm' },
  { name: 'Neuroticism',       color: '#bd0638', lo: 'Calm',        hi: 'Sensitive' },
];

function Big5Bars({ values }: { values: number[] }) {
  return (
    <div>
      {BIG5_TRAITS.map((t, i) => {
        const v = Math.max(0, Math.min(1, values[i] ?? 0));
        const pole = v >= 0.5 ? t.hi : t.lo;
        return (
          <div key={t.name} style={{ marginBottom: 8 }} title={`${t.lo} ↔ ${t.hi}`}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}>
              <span style={{ fontSize: 10.5, color: TXT, fontWeight: 500 }}>{t.name}</span>
              <span style={{ marginLeft: 'auto', fontSize: 9.5, color: t.color, letterSpacing: '0.02em' }}>{pole}</span>
              <span style={{ fontSize: 10, color: TXT2, fontVariantNumeric: 'tabular-nums', width: 20, textAlign: 'right' }}>{Math.round(v * 100)}</span>
            </div>
            <div style={{ position: 'relative', height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.06)' }}>
              <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${v * 100}%`, borderRadius: 999, background: t.color, opacity: 0.92 }} />
              <div style={{ position: 'absolute', left: '50%', top: -1.5, bottom: -1.5, width: 1, background: 'rgba(255,255,255,0.22)' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  PER-AGENT PROFILE — who they are (left section)
// ════════════════════════════════════════════════════════════════════════════
export function AgentProfile({ profile, accent = ACCENT }: { profile: any; accent?: string }) {
  const p = profile;
  if (!p) return <div style={{ color: LBL, fontSize: 11, padding: 16 }}>Loading profile…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <Row k="AGE" v={p.minor ? `${p.age} (minor)` : p.age} />
      <Row k="GENDER" v={cap(p.gender)} />
      <Row k="NATIONALITY" v={p.nat} />
      <Row k="PARISH" v={p.parish} />
      {!p.minor && <Row k="EDUCATION" v={cap(p.edu)} />}
      {!p.minor && <Row k="EMPLOYMENT" v={cap(p.emp)} />}
      {!p.minor && <Row k="SECTOR" v={p.sector} />}
      <Row k="INCOME" v={cap(p.inc)} />
      {!p.minor && <Row k="YEARS IN ANDORRA" v={p.yia} />}
      <Row k="HOUSEHOLD" v={cap(p.hh)} />

      {!p.minor && p.big5 && (
        <Section title="Personality (Big Five)" right="┊ avg">
          <Big5Bars values={p.big5} />
        </Section>
      )}

      {!p.minor && p.sv && (
        <Section title="Core values (Schwartz)">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {p.sv.map((v: string, i: number) => v && (
              <Chip key={i} color={i === 0 ? '#3730a3' : '#1f2937'}>{i === 0 ? '★ ' : ''}{cap(v)}</Chip>
            ))}
          </div>
        </Section>
      )}

      {!p.minor && p.becon && (
        <Section title="Behavioral economics">
          <Bar01 label="Loss aversion" value={Math.min(1, (p.becon[0] ?? 0) / 4)} color="#9ca3af" fmt={() => (p.becon[0] ?? 0).toFixed(1) + '×'} />
          <Bar01 label="Present bias" value={p.becon[2]} color="#9ca3af" />
          <Bar01 label="Discount rate" value={p.becon[1]} color="#9ca3af" />
        </Section>
      )}

      {!p.minor && p.goals && (
        <Section title="Goals & narrative">
          {p.sum && <div style={{ fontSize: 11, color: TXT, lineHeight: 1.6, marginBottom: 8, fontStyle: 'italic' }}>“{p.sum}”</div>}
          {p.goals.fear && <Row k="PRIMARY FEAR" v={p.goals.fear} c="#f87171" />}
          {(p.goals.st || []).length > 0 && (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 9, color: LBL, textTransform: 'uppercase', marginBottom: 3 }}>Short-term goals</div>
              {(p.goals.st || []).map((g: string, i: number) => (
                <div key={i} style={{ fontSize: 11, color: TXT, lineHeight: 1.5, paddingLeft: 10, position: 'relative' }}>
                  <span style={{ position: 'absolute', left: 0, color: ACCENT }}>·</span>{g}
                </div>
              ))}
            </div>
          )}
          {(p.goals.lt || []).length > 0 && (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 9, color: LBL, textTransform: 'uppercase', marginBottom: 3 }}>Long-term goals</div>
              {(p.goals.lt || []).map((g: string, i: number) => (
                <div key={i} style={{ fontSize: 11, color: TXT, lineHeight: 1.5, paddingLeft: 10, position: 'relative' }}>
                  <span style={{ position: 'absolute', left: 0, color: '#60a5fa' }}>·</span>{g}
                </div>
              ))}
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  WHAT THEY'RE LIVING — the day + felt state (right section)
// ════════════════════════════════════════════════════════════════════════════
export function AgentJourney({ profile, t }: { profile: any; t: number }) {
  const trips: any[] = profile?.trips || [];
  if (!trips.length) return null;
  return (
    <div>
      <div style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: LBL, fontWeight: 600, marginBottom: 8, display: 'flex' }}>
        Daily journey <span style={{ marginLeft: 'auto', color: LBL }}>{trips.length} trips</span>
      </div>
      <div style={{ position: 'relative', height: 16, borderRadius: 4, background: 'rgba(255,255,255,0.05)', overflow: 'hidden', marginBottom: 6 }}>
        {trips.map((tr, i) => {
          const left = (tr.d / 1440) * 100, w = Math.max(0.4, (tr.du / 1440) * 100);
          return <div key={i} title={`${cap(tr.t)} · ${tr.m} · ${hhmm(tr.d)}`}
            style={{ position: 'absolute', left: `${left}%`, width: `${w}%`, top: 0, bottom: 0, background: ACTIVITY_COLORS[tr.t] || '#64748b' }} />;
        })}
        <div style={{ position: 'absolute', left: `${(t / 1440) * 100}%`, top: -1, bottom: -1, width: 1.5, background: ACCENT }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: LBL, marginBottom: 8 }}>
        <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {trips.map((tr, i) => {
          const active = t >= tr.d && t <= tr.d + tr.du;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, opacity: active ? 1 : 0.7 }}>
              <span style={{ color: active ? ACCENT : LBL, width: 38, fontVariantNumeric: 'tabular-nums' }}>{hhmm(tr.d)}</span>
              <span style={{ width: 7, height: 7, borderRadius: 2, background: ACTIVITY_COLORS[tr.t] || '#64748b', flexShrink: 0 }} />
              <span style={{ color: TXT, flex: 1, textTransform: 'capitalize' }}>{cap(tr.t)}</span>
              <span style={{ color: MODE_COLORS[tr.m] || LBL }}>{tr.m}</span>
              <span style={{ color: LBL, width: 40, textAlign: 'right' }}>{Math.round(tr.du)}min</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function EmotionState({ profile, emotion, emotionColor }:
  { profile: any; emotion: string | null; emotionColor: string }) {
  const drivers = emotionDrivers(profile);
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: LBL, fontWeight: 600 }}>Felt state</span>
        {emotion && <span style={{ marginLeft: 'auto', color: emotionColor, fontWeight: 600, fontSize: 12 }}>{emotion}</span>}
      </div>
      {drivers.length > 0
        ? drivers.slice(0, 4).map(d => <Bar01 key={d.driver} label={d.driver} value={d.weight} color="#9ca3af" />)
        : <div style={{ fontSize: 11, color: LBL }}>No psychometric drivers (minor).</div>}
    </div>
  );
}

// Paul Ekman 3D emotion bubbles — one sphere per emotion, sized by the (placeholder)
// mood vector, dominant emotion centred. Radial gradient + inset highlight/shadow
// gives the spheres depth.
export function EmotionBubbles({ moodVector }: { moodVector: number[] }) {
  const v = (moodVector && moodVector.length === 7) ? moodVector : EKMAN.map(() => 1 / 7);
  const items = EKMAN.map((label, i) => ({ label, color: EKMAN_RGB[i], val: v[i] }))
    .sort((a, b) => b.val - a.val);
  const max = Math.max(...v, 0.001);
  const ringN = Math.max(1, items.length - 1);
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {items.map((it, idx) => {
        const size = 34 + (it.val / max) * 116;
        let cx = 50, cy = 50;
        if (idx > 0) {
          const ang = ((idx - 1) / ringN) * Math.PI * 2 - Math.PI / 2;
          cx = 50 + Math.cos(ang) * 31;
          cy = 50 + Math.sin(ang) * 31;
        }
        return (
          <div key={it.label} title={`${cap(it.label)} ${Math.round(it.val * 100)}%`}
            style={{
              position: 'absolute', left: `${cx}%`, top: `${cy}%`, transform: 'translate(-50%,-50%)',
              width: size, height: size, borderRadius: '50%',
              background: `radial-gradient(circle at 34% 28%, ${it.color}, ${it.color}88 55%, ${it.color}22 100%)`,
              boxShadow: `0 0 ${size * 0.35}px ${it.color}66, inset -2px -3px ${size * 0.3}px rgba(0,0,0,0.35), inset 3px 3px ${size * 0.25}px rgba(255,255,255,0.20)`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.6s cubic-bezier(0.25,0.1,0.25,1)',
            }}>
            <span style={{ fontFamily: TITLE, fontSize: Math.max(8, size * 0.13), color: '#fff', fontWeight: 600, textShadow: '0 1px 3px rgba(0,0,0,0.6)', lineHeight: 1 }}>
              {cap(it.label)}
            </span>
            {size > 58 && <span style={{ fontSize: Math.max(8, size * 0.11), color: 'rgba(255,255,255,0.85)', fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>{Math.round(it.val * 100)}%</span>}
          </div>
        );
      })}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
//  POPULATION DASHBOARDS
// ════════════════════════════════════════════════════════════════════════════
const ChartBox = ({ data, color = ACCENT, height = 90 }: { data: { name: string; v: number }[]; color?: string; height?: number }) => (
  <div style={{ height }}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
        <XAxis dataKey="name" tick={{ fill: LBL, fontSize: 8 }} interval={0} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: LBL, fontSize: 8 }} axisLine={false} tickLine={false} width={32} />
        <Tooltip contentStyle={{ background: '#111827', border: `1px solid ${BDR}`, borderRadius: 6, fontSize: 11 }} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <Bar dataKey="v" fill={color} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  </div>
);

const DashCard = ({ title, children }: any) => (
  <div style={{
    background: CARD, border: `0.5px solid ${GLASS_BDR}`, borderRadius: 16, padding: 16, boxShadow: GLASS_SHADOW,
    backdropFilter: GLASS_BLUR, WebkitBackdropFilter: GLASS_BLUR,
  }}>
    <div style={{ fontFamily: TITLE, fontSize: 12, fontWeight: 500, color: TXT2, marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);

export function PopulationDashboards({ agg }: { agg: any }) {
  if (!agg) return <div style={{ color: LBL, fontSize: 11, padding: 16 }}>Loading population analytics…</div>;
  const m = agg.mobility, pol = agg.political, ec = agg.economic, dem = agg.demographics;

  const modeData = Object.entries(m.mode_share || {}).map(([k, v]) => ({ name: k, v: v as number }));
  const depData = (m.departure_hist_30min || []).map((v: number, i: number) => ({ name: i % 4 === 0 ? hhmm(i * 30) : '', v }));
  const actData = Object.entries(m.activity_mix || {}).filter(([k]) => k !== 'home')
    .map(([k, v]) => ({ name: k.slice(0, 4), v: v as number })).sort((a, b) => b.v - a.v);
  const salData = Object.entries(pol.issue_salience_mean || {}).map(([k, v]) => ({ name: k.slice(0, 4), v: Math.round((v as number) * 100) }));
  const trustData = Object.entries(pol.institutional_trust_mean || {}).map(([k, v]) => ({ name: k.slice(0, 4), v: Math.round((v as number) * 100) }));
  const fsByInc = dem ? (ec.financial_stress_by_income?.order || []).map((b: string) => ({ name: b.slice(0, 4), v: Math.round((ec.financial_stress_by_income.mean[b] ?? 0) * 100) })) : [];

  // demographics realized vs target
  const demoCompare = (block: any, order?: string[]) => {
    const keys = order || Object.keys(block.realized || block);
    return keys.map((k: string) => ({
      name: k.length > 6 ? k.slice(0, 5) : k,
      realized: Math.round((block.realized?.[k] ?? 0) * 100),
      target: Math.round((block.target?.[k] ?? 0) * 100),
    }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 12, color: LBL }}>
        Population analytics · {agg.n_agents?.toLocaleString()} agents ({agg.n_adults?.toLocaleString()} adults)
      </div>

      {/* Mobility & schedule */}
      <DashCard title="Mobility & daily schedule">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>MODE SHARE (trips)</div>
            <ChartBox data={modeData} color="#f87171" height={80} />
          </div>
          <div>
            <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>ACTIVITY MIX</div>
            <ChartBox data={actData} color="#60a5fa" height={80} />
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>DEPARTURES OVER THE DAY (rush-hour peaks)</div>
          <ChartBox data={depData} color="#fbbf24" height={80} />
        </div>
        <div style={{ fontSize: 10, color: LBL, marginTop: 6 }}>
          {m.total_trips?.toLocaleString()} trips · cross-border share {Math.round((m.cross_border_share ?? 0) * 100)}%
        </div>
      </DashCard>

      {/* Political & civic */}
      <DashCard title="Political & civic landscape">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>ISSUE SALIENCE (mean %)</div>
            <ChartBox data={salData} color="#22d3ee" height={80} />
          </div>
          <div>
            <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>INSTITUTIONAL TRUST (mean %)</div>
            <ChartBox data={trustData} color="#a78bfa" height={80} />
          </div>
        </div>
        {/* Political compass heatmap */}
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>POLITICAL COMPASS (economic → · social ↑)</div>
          <Compass grid={pol.compass_12x12} />
        </div>
      </DashCard>

      {/* Economic stress */}
      <DashCard title="Economic stress">
        <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>FINANCIAL STRESS by income bracket (mean %)</div>
        <ChartBox data={fsByInc} color="#fb7185" height={90} />
      </DashCard>

      {/* Demographics vs SAIG */}
      {dem && (
        <DashCard title="Demographics vs SAIG 2023 ground truth">
          <CompareBars title="Nationality (%)" data={demoCompare(dem.nationality)} />
          <CompareBars title="Age band (%)" data={demoCompare(dem.age, dem.age.order)} />
          <CompareBars title="Income bracket (%)" data={demoCompare(dem.income, dem.income.order)} />
        </DashCard>
      )}
    </div>
  );
}

// realized vs target grouped bars
function CompareBars({ title, data }: { title: string; data: { name: string; realized: number; target: number }[] }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 9, color: LBL, marginBottom: 4 }}>{title}</div>
      <div style={{ height: 70 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 2, right: 4, bottom: 0, left: -28 }}>
            <XAxis dataKey="name" tick={{ fill: LBL, fontSize: 8 }} interval={0} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: LBL, fontSize: 8 }} axisLine={false} tickLine={false} width={30} />
            <Tooltip contentStyle={{ background: '#111827', border: `1px solid ${BDR}`, borderRadius: 6, fontSize: 11 }} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="realized" fill={ACCENT} radius={[2, 2, 0, 0]} />
            <Bar dataKey="target" fill="#475569" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// 12×12 political compass heatmap
function Compass({ grid }: { grid: number[][] }) {
  if (!grid?.length) return null;
  const max = Math.max(1, ...grid.flat());
  // grid is [econ_bin][social_bin]; render social ascending upward
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'stretch' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${grid.length}, 1fr)`, gap: 1, flex: 1, aspectRatio: '1.4', background: 'rgba(255,255,255,0.03)' }}>
        {Array.from({ length: grid[0].length }).map((_, s) =>
          grid.map((col, e) => {
            const v = col[grid[0].length - 1 - s] ?? 0;   // flip so social↑
            const a = v / max;
            return <div key={`${e}-${s}`} style={{ background: `rgba(163,230,53,${0.08 + a * 0.9})`, borderRadius: 1 }} title={`${v}`} />;
          })
        )}
      </div>
    </div>
  );
}
