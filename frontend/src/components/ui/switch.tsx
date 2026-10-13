// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { Switch as SwitchPrimitive } from "@base-ui/react/switch";

import { cn } from "@/lib/utils";

type SwitchProps = Omit<SwitchPrimitive.Root.Props, "className" | "children"> & {
  className?: string;
  size?: "sm" | "default" | "lg";
};

/** Shared geometry and theme for every boolean slider; consumers choose only size. */
function Switch({ className, size = "default", ...props }: SwitchProps) {
  return (
    <SwitchPrimitive.Root
      nativeButton
      render={<button type="button" />}
      data-slot="switch"
      data-size={size}
      className={cn(
        "peer relative box-border inline-flex shrink-0 cursor-pointer items-center justify-start rounded-full border-0 bg-input px-0.5 py-0 align-middle leading-none outline-none transition-colors data-checked:bg-primary focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-disabled:cursor-not-allowed data-disabled:opacity-50",
        size === "sm" ? "h-4 w-7" : size === "lg" ? "h-6 w-11" : "h-5 w-9",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block shrink-0 rounded-full bg-white shadow-sm transition-transform motion-reduce:transition-none",
          size === "sm"
            ? "size-3 data-checked:translate-x-3 rtl:data-checked:-translate-x-3"
            : size === "lg"
              ? "size-5 data-checked:translate-x-5 rtl:data-checked:-translate-x-5"
              : "size-4 data-checked:translate-x-4 rtl:data-checked:-translate-x-4",
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch, type SwitchProps };
