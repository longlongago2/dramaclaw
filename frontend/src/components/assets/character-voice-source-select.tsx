// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useCharacterVoiceSelection, useUpdateCharacterVoiceSelection } from "@/lib/queries/character-voice-generation";
import { ASSET_SOURCE_CONTENT_CLASS, ASSET_SOURCE_ITEM_CLASS, ASSET_SOURCE_TRIGGER_CLASS } from "@/components/ui/header-action-styles";

export function CharacterVoiceSourceSelect({ project }: { project: string }) {
  const { t } = useTranslation();
  const query = useCharacterVoiceSelection(project);
  const update = useUpdateCharacterVoiceSelection(project);
  const selection = query.data?.data;
  const entries = Object.entries(selection?.options ?? {});
  return (
    <TooltipProvider delay={80}>
      <Tooltip>
        <TooltipTrigger render={<span className="inline-flex" />}>
          <Select value={selection?.model ?? ""} disabled={query.isLoading || update.isPending || entries.length === 0}
            onValueChange={async (value) => {
              if (!value || value === selection?.model) return;
              try { await update.mutateAsync(value); }
              catch { toast.error(t("characters.voiceGeneration.sourceSaveFailed")); }
            }}>
            <SelectTrigger aria-label={t("characters.voiceGeneration.source")}
              className={ASSET_SOURCE_TRIGGER_CLASS}>
              <span className="shrink-0 text-muted-foreground">{t("characters.voiceGeneration.source")}</span>
              <span className="shrink-0 text-muted-foreground/50">&nbsp;·&nbsp;</span>
              <SelectValue>{selection?.options?.[selection.model] || t("characters.voiceGeneration.noSource")}</SelectValue>
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false} className={ASSET_SOURCE_CONTENT_CLASS}>
              <SelectGroup className="p-0">
                {entries.map(([value, label]) => <SelectItem key={value} value={value} className={ASSET_SOURCE_ITEM_CLASS}>{label}</SelectItem>)}
              </SelectGroup>
            </SelectContent>
          </Select>
        </TooltipTrigger>
        <TooltipContent>{t("characters.voiceGeneration.sourceHint")}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
