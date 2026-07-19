import type { ProjectFeature } from "../types";
import { STAGE_META, stageColor } from "../theme";

interface Props {
  features: ProjectFeature[]; // already filtered
  selectedId: string | null;
  onSelect: (id: string) => void;
  dark: boolean;
}

export default function LeadList({ features, selectedId, onSelect, dark }: Props) {
  const ranked = [...features].sort(
    (a, b) => (b.properties.lead_score ?? 0) - (a.properties.lead_score ?? 0),
  );

  return (
    <div className="leadlist">
      <div className="panel-title">Priority leads ({ranked.length})</div>
      <div className="lead-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Score</th>
              <th>Promoter</th>
              <th>Stage</th>
              <th>Locality</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((f, i) => {
              const p = f.properties;
              const sel = p.project_id === selectedId;
              return (
                <tr
                  key={p.project_id}
                  className={sel ? "sel" : ""}
                  onClick={() => onSelect(p.project_id)}
                >
                  <td className="num">{i + 1}</td>
                  <td className="num score">{p.lead_score ?? "—"}</td>
                  <td>
                    <div className="lead-name">{p.promoter_org || p.name || "(unnamed)"}</div>
                    {p.is_organization && <span className="tag">org</span>}
                  </td>
                  <td>
                    <span className="stage-chip">
                      <span className="chip-dot" style={{ background: stageColor(p.stage, dark) }} />
                      {STAGE_META[p.stage]?.label}
                    </span>
                  </td>
                  <td>
                    {p.village || "—"}
                    <div className="muted">{p.district}</div>
                  </td>
                </tr>
              );
            })}
            {ranked.length === 0 && (
              <tr>
                <td colSpan={5} className="muted center">
                  No projects match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
