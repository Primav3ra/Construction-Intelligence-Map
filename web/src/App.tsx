import { useMemo, useState, useEffect } from "react";
import { useData } from "./useData";
import type { ProjectFeature, Stage } from "./types";
import { STAGE_ORDER } from "./theme";
import MapView from "./components/MapView";
import Filters, { FilterState } from "./components/Filters";
import LeadList from "./components/LeadList";
import ProjectPanel from "./components/ProjectPanel";
import Dashboard from "./components/Dashboard";

function usePrefersDark() {
  const [dark, setDark] = useState<boolean>(
    () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false,
  );
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  return [dark, setDark] as const;
}

export default function App() {
  const state = useData();
  const [dark, setDark] = usePrefersDark();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    stages: new Set<Stage>(STAGE_ORDER),
    district: "",
    minScore: 0,
    query: "",
  });

  const allFeatures: ProjectFeature[] =
    state.status === "ready" ? state.data.geo.features : [];

  const filtered = useMemo(() => {
    const q = filters.query.trim().toLowerCase();
    return allFeatures.filter((f) => {
      const p = f.properties;
      if (!filters.stages.has(p.stage)) return false;
      if (filters.district && p.district !== filters.district) return false;
      if ((p.lead_score ?? 0) < filters.minScore) return false;
      if (q && !(`${p.promoter_org} ${p.name} ${p.village}`.toLowerCase().includes(q)))
        return false;
      return true;
    });
  }, [allFeatures, filters]);

  const selected =
    filtered.find((f) => f.properties.project_id === selectedId)?.properties ??
    allFeatures.find((f) => f.properties.project_id === selectedId)?.properties ??
    null;

  if (state.status === "loading") return <div className="fullmsg">Loading construction signals…</div>;
  if (state.status === "error")
    return (
      <div className="fullmsg error">
        Could not load data artifacts.<br />
        <small>Run the pipeline to generate <code>data/*.json</code>, then copy into <code>web/public/data/</code>.</small>
        <br /><small>{state.error}</small>
      </div>
    );

  const meta = state.data.meta;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◧</span>
          <div>
            <div className="title">Hyderabad Construction Intelligence</div>
            <div className="subtitle">
              Cement-demand leads from public building permits · HMDA growth corridors
            </div>
          </div>
        </div>
        <div className="topbar-right">
          <div className="refresh">
            <span className="dot live" /> Refreshed {meta.generated_at.slice(0, 10)} ·
            {" "}{meta.refresh_cadence} · {meta.record_count} projects
          </div>
          <button className="theme-toggle" onClick={() => setDark(!dark)}>
            {dark ? "☀ Light" : "☾ Dark"}
          </button>
        </div>
      </header>

      <Filters
        filters={filters}
        setFilters={setFilters}
        meta={meta}
        dark={dark}
        shown={filtered.length}
        total={allFeatures.length}
      />

      <main className="grid">
        <section className="col-map">
          <MapView features={filtered} selectedId={selectedId} onSelect={setSelectedId} dark={dark} />
          <Dashboard features={filtered} dark={dark} />
        </section>
        <aside className="col-side">
          <LeadList features={filtered} selectedId={selectedId} onSelect={setSelectedId} dark={dark} />
          <ProjectPanel project={selected} dark={dark} onClose={() => setSelectedId(null)} />
        </aside>
      </main>

      <footer className="foot">{meta.disclaimer}</footer>
    </div>
  );
}
