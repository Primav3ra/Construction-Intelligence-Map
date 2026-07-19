import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { ProjectFeature } from "../types";
import { STAGE_ORDER, STAGE_META, stageColor } from "../theme";

interface Props {
  features: ProjectFeature[];
  dark: boolean;
}

export default function Dashboard({ features, dark }: Props) {
  const ink = dark ? "#c3c2b7" : "#52514e";

  // stage mix (fixed order)
  const stageCounts = STAGE_ORDER.map((s) => ({
    stage: s,
    label: STAGE_META[s].label,
    count: features.filter((f) => f.properties.stage === s).length,
  })).filter((d) => d.count > 0);

  // top promoters by project count (repeat-buyer signal)
  const promoterMap = new Map<string, number>();
  for (const f of features) {
    const name = f.properties.promoter_org;
    if (name) promoterMap.set(name, (promoterMap.get(name) ?? 0) + 1);
  }
  const topPromoters = [...promoterMap.entries()]
    .map(([name, count]) => ({ name: name.length > 22 ? name.slice(0, 21) + "…" : name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
    .filter((d) => d.count > 0);

  return (
    <div className="dashboard">
      <div className="chart-card">
        <div className="panel-title">Stage mix</div>
        <ResponsiveContainer width="100%" height={170}>
          <BarChart data={stageCounts} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: ink }} interval={0} angle={-12} dy={8} height={42} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: ink }} />
            <Tooltip cursor={{ fillOpacity: 0.08 }} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {stageCounts.map((d) => (
                <Cell key={d.stage} fill={stageColor(d.stage, dark)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <div className="panel-title">Top promoters (repeat = warmer lead)</div>
        <ResponsiveContainer width="100%" height={170}>
          <BarChart data={topPromoters} layout="vertical" margin={{ top: 6, right: 12, bottom: 0, left: 8 }}>
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: ink }} />
            <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10, fill: ink }} />
            <Tooltip cursor={{ fillOpacity: 0.08 }} />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} fill={dark ? "#3987e5" : "#2a78d6"} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
