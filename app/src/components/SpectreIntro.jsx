import { useEffect, useState, useCallback } from 'react';

// Hard-reset boot sequence: dark gradient screen, "SPECTRE" in metallic Syne. It holds
// on screen until the user clicks (or presses Enter/Space), then fades out and hands off
// to the Earth globe. onComplete fires once.
export default function SpectreIntro({ onComplete }) {
  const [leaving, setLeaving] = useState(false);
  const [hint, setHint]       = useState(false);

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
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey); };
  }, [dismiss]);

  return (
    <div
      className={`spectre-intro ${leaving ? 'is-leaving' : ''}`}
      onClick={dismiss}
      role="button"
      tabIndex={0}
    >
      <div className="spectre-intro-inner">
        <h1 className="spectre-wordmark">SPECTRE</h1>
        <p className="spectre-subtitle">Sovereign Decision Intelligence</p>
      </div>
      <p className={`spectre-hint ${hint ? 'show' : ''}`}>Click anywhere to enter</p>
    </div>
  );
}
