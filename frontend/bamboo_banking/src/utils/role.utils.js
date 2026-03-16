import { ROLE_LABELS } from "../constants/header.constants";

export function formatRoleLabel(role) {
  if (!role || typeof role !== "string") return ROLE_LABELS.user;

  const normalized = role.trim().toLowerCase();
  return ROLE_LABELS[normalized] ?? normalized.replace(/_/g, " ");
}
