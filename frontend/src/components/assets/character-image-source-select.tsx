// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  type AssetImageSourceKind,
  useAssetImageSourceSelection,
  useUpdateAssetImageSourceSelection,
} from "@/lib/queries/character-image-selection";
import { cn } from "@/lib/utils";
import { ASSET_SOURCE_CONTENT_CLASS, ASSET_SOURCE_ITEM_CLASS, ASSET_SOURCE_TRIGGER_CLASS } from "@/components/ui/header-action-styles";

export type CharacterImageSourceSelectProps = {
  project: string;
  kind?: AssetImageSourceKind;
  className?: string;
  disabled?: boolean;
  onSelectionChange?: (selection: string) => void;
};

export function CharacterImageSourceSelect({
  project,
  kind = "character",
  className,
  disabled,
  onSelectionChange,
}: CharacterImageSourceSelectProps) {
  const { t } = useTranslation();
  const selectionQuery = useAssetImageSourceSelection(project, kind);
  const updateSelection = useUpdateAssetImageSourceSelection(project, kind);
  const selection = selectionQuery.data?.data.image_source_selection ?? "";
  const options = selectionQuery.data?.data.options ?? {};
  const optionEntries = Object.entries(options);
  const selectedLabel = options[selection] ?? selection;
  const isDisabled =
    disabled ||
    selectionQuery.isLoading ||
    (selectionQuery.isFetching && !selectionQuery.data) ||
    updateSelection.isPending;

  const handleValueChange = async (value: string | null) => {
    if (!value || value === selection || updateSelection.isPending) return;
    try {
      await updateSelection.mutateAsync(value);
      onSelectionChange?.(value);
    } catch {
      toast.error(t("characters.imageSource.saveFailed"));
    }
  };

  return (
    <Select
      value={selection}
      disabled={isDisabled}
      onValueChange={handleValueChange}
    >
      <SelectTrigger
        aria-label={t("characters.imageSource.label")}
        className={cn(
          ASSET_SOURCE_TRIGGER_CLASS,
          className,
        )}
        disabled={isDisabled}
      >
        <span className="shrink-0 text-muted-foreground">
          {t("characters.imageSource.label")}
        </span>
        <span className="shrink-0 text-muted-foreground/50">&nbsp;·&nbsp;</span>
        <SelectValue>
          {selectedLabel || t("characters.imageSource.loading")}
        </SelectValue>
      </SelectTrigger>
      <SelectContent
        alignItemWithTrigger={false}
        className={ASSET_SOURCE_CONTENT_CLASS}
      >
        <SelectGroup className="p-0">
          {optionEntries.map(([value, label]) => (
            <SelectItem
              key={value}
              value={value}
              className={ASSET_SOURCE_ITEM_CLASS}
            >
              {label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
