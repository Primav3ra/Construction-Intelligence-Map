import type { Stage, Meta } from "../types";
import { STAGE_ORDER, STAGE_META, stageColor } from "../theme";

export interface FilterState {
  stages: Set<Stage>;
  district: string;
  minScore: number;
  query: string;
}

interface Props {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  meta: Meta;
  dark: boolean;
  shown: number;
  total: number;
}

export default function Filters({ filters, setFilters, meta, dark, shown, total }: Props) {
  const toggleStage = (s: Stage) => {
    const next = new Set(filters.stages);
    next.has(s) ? next.delete(s) : next.add(s);
    setFilters({ ...filters, stages: next });
  };
  const districts = Object.keys(meta.by_district).sort();

  return (
    <div className="filters">
      <div className="filter-group stages">
        {STAGE_ORDER.map((s) => {
          const on = filters.stages.has(s);
          return (
            <button
              key={s}
              className={`chip ${on ? "on" : ""}`}
              onClick={() => toggleStage(s)}
              title={STAGE_META[s].blurb}
              aria-pressed={on}
            >
              <span className="chip-dot" style={{ background: stageColor(s, dark) }} />
              {STAGE_META[s].label}
            </button>
          );
        })}
      </div>

      <div className="filter-group">
        <label>
          District
          <select
            value={filters.district}
            onChange={(e) => setFilters({ ...filters, district: e.target.value })}
          >
            <option value="">All ({total})</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d} ({meta.by_district[d]})
              </option>
            ))}
          </select>
        </label>

        <label>
          Min score: <b>{filters.minScore}</b>
          <input
            type="range"
            min={0}
            max={100}
            value={filters.minScore}
            onChange={(e) => setFilters({ ...filters, minScore: Number(e.target.value) })}
          />
        </label>

        <label>
          Search
          <input
            type="search"
            placeholder="promoter / village"
            value={filters.query}
            onChange={(e) => setFilters({ ...filters, query: e.target.value })}
          />
        </label>
      </div>

      <div className="filter-count">
        Showing <b>{shown}</b> of {total}
      </div>
    </div>
  );
}
