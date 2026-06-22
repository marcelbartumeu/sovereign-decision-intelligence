import { useEffect, useState, useCallback } from 'react';

// Hard-reset boot sequence: dark gradient screen, "SPECTRE" in metallic Syne, and a
// faux secure-uplink terminal that streams clearance lines. It holds on screen until
// the user clicks (or presses Enter/Space), then fades out and hands off to the Earth
// globe. onComplete fires once.
const BOOT_LINES = [
  { t: '> ESTABLISHING SECURE UPLINK', s: 'OK' },
  { t: '> AUTHENTICATING CLEARANCE · LEVEL 9', s: 'GRANTED' },
  { t: '> DECRYPTING ANDORRA DATASET', s: 'OK' },
  { t: '> SYNCING SCENARIO MODELS · 5 BRANCHES', s: 'OK' },
  { t: '> SOVEREIGN DECISION INTELLIGENCE', s: 'ONLINE' },
];

export default function SpectreIntro({ onComplete }) {
  const [leaving, setLeaving] = useState(false);
  const [hint, setHint]       = useState(false);
  const [shown, setShown]     = useState(0); // how many boot lines are revealed

  const dismiss = useCallback(() => {
    setLeaving((prev) => {
      if (prev) return prev;
      setTimeout(() => onComplete?.(), 760);
      return true;
    });
  }, [onComplete]);

  useEffect(() => {
    const t = setTimeout(() => setHint(true), 1500);
    const onKey = (e) => { if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') dismiss(); };
    window.addEventListener('keydown', onKey);
    // Stream the boot lines in, one every ~360ms after a short delay.
    const reveal = setInterval(() => {
      setShown((n) => (n >= BOOT_LINES.length ? n : n + 1));
    }, 360);
    return () => { clearTimeout(t); clearInterval(reveal); window.removeEventListener('keydown', onKey); };
  }, [dismiss]);

  return (
    <div
      className={`spectre-intro ${leaving ? 'is-leaving' : ''}`}
      onClick={dismiss}
      role="button"
      tabIndex={0}
    >
      {/* Intro-scoped corner brackets so the boot reads as a framed terminal */}
      <span className="hud-bracket tl" />
      <span className="hud-bracket tr" />
      <span className="hud-bracket bl" />
      <span className="hud-bracket br" />
      <div className="spectre-intro-inner">
        <h1 className="spectre-wordmark">SPECTRE</h1>
        <p className="spectre-subtitle">Sovereign Decision Intelligence</p>
        <div className="boot-terminal">
          {BOOT_LINES.slice(0, shown).map((l, i) => (
            <div key={i}>
              {l.t} <span className="ok">[{l.s}]</span>
            </div>
          ))}
          {shown < BOOT_LINES.length && <span className="caret">█</span>}
        </div>
      </div>
      <p className={`spectre-hint ${hint ? 'show' : ''}`}>Click anywhere to enter</p>
    </div>
  );
}
