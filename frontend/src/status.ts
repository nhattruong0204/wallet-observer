export type ApplicationStatus = {
  mode: "fixture" | "live";
  database: "ready" | "unavailable";
  collection: "disabled";
  notifications: "disabled";
};

export function parseStatus(value: unknown): ApplicationStatus {
  if (typeof value !== "object" || value === null) throw new Error("Invalid status");
  const status = value as Record<string, unknown>;
  if (
    !["fixture", "live"].includes(String(status.mode)) ||
    !["ready", "unavailable"].includes(String(status.database)) ||
    status.collection !== "disabled" ||
    status.notifications !== "disabled"
  )
    throw new Error("Invalid status");
  return {
    mode: status.mode as ApplicationStatus["mode"],
    database: status.database as ApplicationStatus["database"],
    collection: "disabled",
    notifications: "disabled",
  };
}
