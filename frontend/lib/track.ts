// AMI-66 funnel instrumentation. No analytics platform exists in this repo
// yet — this is a minimal typed stub per the spec's fallback guidance.
// TODO: wire to a real analytics sink (e.g. PostHog) once one is adopted.
export type VitalsFunnelEvent =
  | "vitals_prompt_viewed"
  | "vitals_path_selected"
  | "vitals_started"
  | "vitals_validation_error"
  | "vitals_completed"
  | "profile_estimated_viewed"
  | "statement_import_started"
  | "statement_import_completed"
  | "import_cta_clicked";

export function track(event: VitalsFunnelEvent, props?: Record<string, unknown>): void {
  if (process.env.NODE_ENV !== "production") {
    console.info(`[track] ${event}`, props ?? {});
  }
}
