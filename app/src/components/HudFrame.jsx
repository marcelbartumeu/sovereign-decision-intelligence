// Global heads-up-display overlay: scanlines, vignette, hairline frame and the
// four gold corner brackets that frame the entire console. Rendered once at the
// top of the app shell. pointer-events:none throughout, so it never intercepts
// clicks, hovers or map interaction underneath.
export default function HudFrame() {
  return (
    <div className="hud-frame" aria-hidden="true">
      <div className="hud-vignette" />
      <div className="hud-scan" />
      <div className="hud-edge" />
      <span className="hud-bracket tl" />
      <span className="hud-bracket tr" />
      <span className="hud-bracket bl" />
      <span className="hud-bracket br" />
    </div>
  );
}
