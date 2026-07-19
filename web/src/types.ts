// Shapes mirror the pipeline's export artifacts (pipeline/export.py).

export type Stage =
  | "likely_active"
  | "approved"
  | "completed"
  | "stale_unknown"
  | "unknown";

export interface SourceRef {
  source: string;
  file_no: string;
  permit_number: string;
  project_type: string;
  fetched_at: string;
}

export interface ScoreBreakdown {
  stage: number;
  recency: number;
  scale: number;
  proximity: number;
  promoter_rep: number;
}

export interface ProjectProps {
  project_id: string;
  name: string;
  promoter_org: string;
  is_organization: boolean;
  district: string;
  village: string;
  category: string;
  permission_types: string[];
  permission_date: string | null;
  oc_date: string | null;
  stage: Stage;
  stage_confidence: "high" | "medium" | "low" | "";
  stage_rule: string;
  geo_confidence: "village" | "district" | "mandal" | "none" | string;
  lead_score: number | null;
  score_breakdown: ScoreBreakdown;
  sources: SourceRef[];
}

export interface ProjectFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] }; // [lng, lat]
  properties: ProjectProps;
}

export interface ProjectsGeoJSON {
  type: "FeatureCollection";
  features: ProjectFeature[];
}

export interface Lead {
  project_id: string;
  lead_score: number;
  name: string;
  promoter_org: string;
  is_organization: boolean;
  district: string;
  village: string;
  stage: Stage;
  stage_confidence: string;
  permission_date: string | null;
  geo_confidence: string;
  score_breakdown: ScoreBreakdown;
  file_no: string;
}

export interface Meta {
  generated_at: string;
  refresh_cadence: string;
  record_count: number;
  mapped_count: number;
  geo_coverage_pct: number;
  by_stage: Record<string, number>;
  by_district: Record<string, number>;
  by_geo_confidence: Record<string, number>;
  sources: string[];
  disclaimer: string;
}
