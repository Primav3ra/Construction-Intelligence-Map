import type { ProjectProps } from "../types";
import { STAGE_META, stageColor, CONFIDENCE_LABEL, SCORE_FACTOR_LABEL } from "../theme";

interface Props {
  project: ProjectProps | null;
  dark: boolean;
  onClose: () => void;
}

export default function ProjectPanel({ project, dark, onClose }: Props) {
  if (!project) {
    return (
      <div className="panel project-panel empty">
        <div className="muted">Select a project on the map or lead list to see its
          demand signal and data provenance.</div>
      </div>
    );
  }
  const p = project;
  const factors = Object.entries(p.score_breakdown) as [keyof typeof p.score_breakdown, number][];

  return (
    <div className="panel project-panel">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <div className="pp-head">
        <div className="pp-name">{p.promoter_org || p.name || "(unnamed)"}</div>
        {p.is_organization && <span className="tag">organization</span>}
      </div>

      <div className="pp-row">
        <span className="stage-chip big">
          <span className="chip-dot" style={{ background: stageColor(p.stage, dark) }} />
          {STAGE_META[p.stage]?.label}
        </span>
        {p.stage_confidence && (
          <span className={`conf ${p.stage_confidence}`}>
            {CONFIDENCE_LABEL[p.stage_confidence] ?? p.stage_confidence}
          </span>
        )}
        <span className="score-big">{p.lead_score ?? "—"}<small>/100</small></span>
      </div>

      <p className="pp-blurb">{STAGE_META[p.stage]?.blurb}</p>

      <div className="pp-grid">
        <div><span className="k">Locality</span>{p.village || "—"}, {p.district}</div>
        <div><span className="k">Geo precision</span>
          <span className={`badge geo-${p.geo_confidence}`}>{p.geo_confidence}</span>
        </div>
        <div><span className="k">Permission date</span>{p.permission_date ?? "—"}</div>
        <div><span className="k">OC date</span>{p.oc_date ?? "—"}</div>
        <div><span className="k">Category</span>{p.category}</div>
        <div><span className="k">Architect/SE</span>{(p as any).architect_se || "—"}</div>
      </div>

      <div className="pp-section">
        <div className="pp-sub">Why this score</div>
        {factors.map(([k, v]) => (
          <div className="factor" key={k}>
            <span className="factor-label">{SCORE_FACTOR_LABEL[k] ?? k}</span>
            <span className="factor-bar">
              <span className="factor-fill" style={{ width: `${Math.round(v * 100)}%` }} />
            </span>
            <span className="factor-val">{Math.round(v * 100)}</span>
          </div>
        ))}
      </div>

      <div className="pp-section transparency">
        <div className="pp-sub">Data provenance</div>
        <div className="prov-rule">
          Stage inferred by rule <code>{p.stage_rule}</code> — an inference from public
          records, not a confirmation of on-site construction.
        </div>
        <table className="sources">
          <thead>
            <tr><th>Source</th><th>File / Permit</th><th>Type</th><th>Fetched</th></tr>
          </thead>
          <tbody>
            {p.sources.map((s, i) => (
              <tr key={i}>
                <td>{s.source}</td>
                <td className="mono">{s.file_no || s.permit_number || "—"}</td>
                <td>{s.project_type}</td>
                <td>{(s.fetched_at || "").slice(0, 10) || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
