import { useEffect, useState } from "react";
import type { ProjectsGeoJSON, Lead, Meta } from "./types";

export interface DataBundle {
  geo: ProjectsGeoJSON;
  leads: Lead[];
  meta: Meta;
}

type State =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: DataBundle };

export function useData(): State {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const base = import.meta.env.BASE_URL || "/";
    const url = (f: string) => `${base}data/${f}`;
    Promise.all([
      fetch(url("projects.geojson")).then((r) => r.json()),
      fetch(url("leads.json")).then((r) => r.json()),
      fetch(url("meta.json")).then((r) => r.json()),
    ])
      .then(([geo, leads, meta]) =>
        setState({ status: "ready", data: { geo, leads, meta } }),
      )
      .catch((e) => setState({ status: "error", error: String(e) }));
  }, []);

  return state;
}
