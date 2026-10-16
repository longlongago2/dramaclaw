// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { describe, expect, it } from "vitest";

import {
  PROJECT_NAME_MAX_LENGTH,
  getProjectNameValidationKey,
} from "@/lib/project-name";

describe("项目名称长度校验", () => {
  it("接受 64 字符名称", () => {
    expect(PROJECT_NAME_MAX_LENGTH).toBe(64);
    expect(getProjectNameValidationKey("a".repeat(64))).toBeNull();
  });

  it("拒绝 65 字符名称", () => {
    expect(getProjectNameValidationKey("a".repeat(65))).toBe("project.nameTooLong");
  });

  it.each(["火柴人", "火柴人 第 1 集", "Un projet français", "🎬".repeat(64), "Cafe\u0301"])(
    "accepts display names in any language: %s", (name) => {
      expect(getProjectNameValidationKey(name)).toBeNull();
    },
  );

  it.each(["", "   ", "a\nb", "a\u0000b", "a\u2028b", "a\ud800b"])(
    "rejects blank or multiline display names: %s", (name) => {
      expect(getProjectNameValidationKey(name)).toBe("project.nameInvalid");
    },
  );

  it("counts Unicode code points for the same limit as the backend", () => {
    expect(getProjectNameValidationKey("🎬".repeat(65))).toBe("project.nameTooLong");
  });
});
