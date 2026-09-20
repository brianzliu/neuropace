export const themes = [
  { id: "pocket", name: "Pocket Studio", description: "White, butter yellow, and rounded lettering.", material: "Tactile & bright" },
  { id: "paper", name: "Paper Playground", description: "Layered paper, raspberry tabs, soft yellow.", material: "Loose & expressive" },
  { id: "orbit", name: "Orbit", description: "Midnight blue, frosted glass, floating rings.", material: "Calm & dimensional" },
];

export default function Appearance({ theme, onChange }: { theme: string; onChange: (theme: string) => void }) {
  return <details className="appearance-menu">
    <summary><span className="appearance-dot" />{themes.find(t => t.id === theme)?.name}<span aria-hidden="true">⌄</span></summary>
    <div className="appearance-options" role="group" aria-label="Choose your workspace design">
      <p>Make yourself at home.</p>
      {themes.map(t => <button key={t.id} className={"theme-option theme-" + t.id} aria-pressed={theme === t.id} onClick={(e) => { onChange(t.id); e.currentTarget.closest("details")?.removeAttribute("open"); }}>
        <span className="theme-miniature" aria-hidden="true"><i /><b /><em /></span>
        <span><strong>{t.name}</strong><small>{t.description}</small></span>
        <span className="theme-check" aria-hidden="true">{theme === t.id ? "✓" : ""}</span>
      </button>)}
      <small className="appearance-hint">Applies across your workspace. Saved on this device.</small>
    </div>
  </details>;
}
