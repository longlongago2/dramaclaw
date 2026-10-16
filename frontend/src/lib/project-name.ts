// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import type { ProjectSummary } from "@/types/project";

export const PROJECT_NAME_MAX_LENGTH = 64;

export function normalizeProjectDisplayName(name: string): string {
  return name.normalize("NFC").trim();
}

export function getProjectNameValidationKey(value: string): string | null {
  const name = normalizeProjectDisplayName(value);
  if (Array.from(name).length > PROJECT_NAME_MAX_LENGTH) return "project.nameTooLong";
  return !name || /[\p{Cc}\p{Cs}\p{Zl}\p{Zp}]/u.test(name) ? "project.nameInvalid" : null;
}

export function getProjectDisplayName(project: Pick<ProjectSummary, "name" | "displayName">): string {
  return project.displayName || project.name;
}
