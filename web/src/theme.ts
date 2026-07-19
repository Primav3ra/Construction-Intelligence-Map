// Colors from the validated data-viz reference palette (categorical slots 1-4 + neutral).
// Stage = identity encoding on the map; legend + lead-list table satisfy the
// contrast relief rule. Marker size (by lead score) is the secondary encoding.

import type { Stage } from "./types";

export interface StageMeta {
  key: Stage;
  label: string;
  light: string;
  dark: string;
  blurb: string;
}

// Fixed order (never cycled). Ordered by cement-demand priority for the legend.
export const STAGE_ORDER: Stage[] = [
  "likely_active",
  "approved",
  "completed",
  "stale_unknown",
  "unknown",
];

export const STAGE_META: Record<Stage, StageMeta> = {
  likely_active: {
    key: "likely_active",
    label: "Likely active",
    light: "#2a78d6",
    dark: "#3987e5",
    blurb: "Permit aged into the build window, no OC yet — structural phase, PEAK cement demand.",
  },
  approved: {
    key: "approved",
    label: "Approved",
    light: "#008300",
    dark: "#008300",
    blurb: "Recent permission, no OC — pre-construction, demand imminent.",
  },
  completed: {
    key: "completed",
    label: "Completed",
    light: "#e87ba4",
    dark: "#d55181",
    blurb: "Occupancy Certificate issued — cement demand largely spent.",
  },
  stale_unknown: {
    key: "stale_unknown",
    label: "Stale / unknown",
    light: "#eda100",
    dark: "#c98500",
    blurb: "Old permission, still no OC — may be stalled, lapsed, or unrecorded.",
  },
  unknown: {
    key: "unknown",
    label: "Unknown",
    light: "#898781",
    dark: "#898781",
    blurb: "Record present but no usable date to infer a stage.",
  },
};

export function stageColor(stage: Stage, dark: boolean): string {
  const m = STAGE_META[stage] ?? STAGE_META.unknown;
  return dark ? m.dark : m.light;
}

export const CONFIDENCE_LABEL: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export const SCORE_FACTOR_LABEL: Record<string, string> = {
  stage: "Lifecycle stage",
  recency: "Recency",
  scale: "Project scale",
  proximity: "Territory proximity",
  promoter_rep: "Promoter repetition",
};

// HMDA jurisdiction rough center (map default view)
export const MAP_CENTER: [number, number] = [17.55, 78.5];
export const MAP_ZOOM = 10;
