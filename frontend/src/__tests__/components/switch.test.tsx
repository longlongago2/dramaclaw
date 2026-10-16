// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Switch, type SwitchProps } from "@/components/ui/switch";

describe("shared Switch", () => {
  it.each(["sm", "default", "lg"] as const)("supports pointer and keyboard interaction at %s size", async (size) => {
    const user = userEvent.setup();
    function Host() {
      const [checked, setChecked] = useState(false);
      return <Switch size={size} aria-label="Enable" checked={checked} onCheckedChange={setChecked} />;
    }
    render(<Host />);
    const control = screen.getByRole("switch", { name: "Enable" });
    expect(control).toHaveAttribute("aria-checked", "false");
    await user.click(control);
    expect(control).toHaveAttribute("aria-checked", "true");
    await user.keyboard(" ");
    expect(control).toHaveAttribute("aria-checked", "false");
    await user.keyboard("{Enter}");
    expect(control).toHaveAttribute("aria-checked", "true");
  });

  it("does not change disabled or read-only controls", async () => {
    const user = userEvent.setup();
    const change = vi.fn();
    render(<><Switch disabled checked aria-label="Disabled" onCheckedChange={change} /><Switch readOnly checked aria-label="Read only" onCheckedChange={change} /></>);
    await user.click(screen.getByRole("switch", { name: "Disabled" }));
    await user.click(screen.getByRole("switch", { name: "Read only" }));
    expect(change).not.toHaveBeenCalled();
  });

  it("preserves existing click handlers without duplicate activation", async () => {
    const user = userEvent.setup();
    const clicked = vi.fn();
    function Host() {
      const [checked, setChecked] = useState(false);
      const click: SwitchProps["onClick"] = () => { clicked(); setChecked((previous) => !previous); };
      return <label>Audio<Switch aria-label="Audio" checked={checked} onClick={click} /></label>;
    }
    render(<Host />);
    await user.click(screen.getByText("Audio"));
    expect(clicked).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("switch", { name: "Audio" })).toHaveAttribute("aria-checked", "true");
  });

  it("does not submit a surrounding form", async () => {
    const submit = vi.fn((event) => event.preventDefault());
    render(<form onSubmit={submit}><Switch defaultChecked aria-label="Toggle" /></form>);
    await userEvent.setup().click(screen.getByRole("switch", { name: "Toggle" }));
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole("switch", { name: "Toggle" })).toHaveAttribute("aria-checked", "false");
  });
});
