const TABS = [
  { id: 'main',           label: 'Overview' },
  { id: 'economic',       label: 'Economic' },
  { id: 'social',         label: 'Social' },
  { id: 'environmental',  label: 'Environment' },
  { id: 'infrastructure', label: 'Infrastructure' },
  { id: 'agents',         label: 'Agents' },
];

export default function TabNav({ activeTab, setActiveTab }) {
  return (
    <div className="tab-nav">
      {TABS.map((tab) => (
        <button
          type="button"
          key={tab.id}
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => setActiveTab(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
