// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AudioLines, Check, Clock3, Headphones, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { resolveMediaUrl } from "@/lib/media-url";
import { cn } from "@/lib/utils";
import { useCharacterVoicePreviews, useCharacterVoiceSelection, useGenerateCharacterVoice, useSaveCharacterVoicePreview } from "@/lib/queries/character-voice-generation";
import type { CharacterVoiceSlot } from "@/types/character";

export function CharacterVoiceGenerateDialog({ project, name, slot, hasVoicePrompt, onClose }: {
  project: string; name: string; slot: CharacterVoiceSlot; hasVoicePrompt: boolean; onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const selection = useCharacterVoiceSelection(project).data?.data;
  const history = useCharacterVoicePreviews(project, name, String(slot.slot));
  const generate = useGenerateCharacterVoice(project, name);
  const save = useSaveCharacterVoicePreview(project, name);
  const [text, setText] = useState(() => t("characters.voiceGeneration.sampleText"));
  const [speaker, setSpeaker] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const previews = history.data?.data ?? [];
  const preview = previews.find((item) => item.preview_id === selectedId)
    ?? previews.find((item) => slot.sha256 && item.sha256 === slot.sha256)
    ?? previews[0];
  const pending = generate.isPending || save.isPending;
  const canGenerate = Boolean(selection?.model && hasVoicePrompt && text.trim() && !pending);
  const handleGenerate = async () => {
    if (!canGenerate) return;
    try {
      const response = await generate.mutateAsync({ slot: String(slot.slot), text: text.trim(), speaker: speaker.trim() });
      if (response.ok) setSelectedId(response.data.preview_id);
      else toast.error(response.error || t("characters.voiceGeneration.failed"));
    } catch { toast.error(t("characters.voiceGeneration.failed")); }
  };
  const handleSave = async () => {
    if (!preview || pending) return;
    try {
      const response = await save.mutateAsync({ slot: String(slot.slot), previewId: preview.preview_id });
      if (!response.ok) { toast.error(response.error || t("characters.voiceGeneration.saveFailed")); return; }
      toast.success(t("characters.voiceGeneration.saved"));
      onClose();
    } catch { toast.error(t("characters.voiceGeneration.saveFailed")); }
  };
  const formatDate = (value: string) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString(i18n.language, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  };
  return (
    <Dialog open onOpenChange={(open) => { if (!open && !pending) onClose(); }}>
      <DialogContent className="flex max-h-[90dvh] flex-col overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="gap-2 border-b px-5 py-4 pr-12">
          <DialogTitle className="flex items-center gap-2">
            <AudioLines className="size-4 text-primary" />
            {t("characters.voiceGeneration.title", { name })}
          </DialogTitle>
          <DialogDescription>{t("characters.voiceGeneration.auditionHint")}</DialogDescription>
        </DialogHeader>
        <div className="grid min-h-0 gap-5 overflow-y-auto px-5 pb-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="size-1.5 rounded-full bg-primary" />
              {t("characters.voiceGeneration.source")} · {selection?.options[selection.model] || t("characters.voiceGeneration.noSource")}
            </p>
            <div className="flex flex-col gap-2">
              <Label htmlFor="character-voice-text">{t("characters.voiceGeneration.text")}</Label>
              <Textarea id="character-voice-text" value={text} disabled={pending} maxLength={1500}
                className="min-h-32 resize-y" onChange={(event) => setText(event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="character-voice-speaker">{t("characters.voiceGeneration.speaker")}</Label>
              <Input id="character-voice-speaker" value={speaker} disabled={pending} maxLength={255}
                placeholder={t("characters.voiceGeneration.speakerPlaceholder")}
                onChange={(event) => setSpeaker(event.target.value)} />
            </div>
            <span className="inline-flex" title={!hasVoicePrompt ? t("characters.voiceGeneration.promptRequired") : undefined}>
              <Button variant="outline" className="w-full" onClick={() => void handleGenerate()} disabled={!canGenerate}>
                {generate.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                {t(generate.isPending ? "characters.voiceGeneration.generating" : "characters.voiceGeneration.generate")}
              </Button>
            </span>
          </div>
          <section className="flex min-w-0 flex-col gap-3" aria-label={t("characters.voiceGeneration.history")}>
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-medium">
                <Headphones className="size-4 text-muted-foreground" />
                {t("characters.voiceGeneration.history")}
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{previews.length}</span>
              </h3>
              <Button variant="ghost" size="icon-sm" aria-label={t("characters.voiceGeneration.refreshHistory")}
                disabled={history.isFetching} onClick={() => void history.refetch()}>
                <RefreshCw className={cn("size-3.5", history.isFetching && "animate-spin")} />
              </Button>
            </div>
            {history.isPending && <p role="status" className="py-8 text-center text-xs text-muted-foreground">{t("common.loading")}</p>}
            {history.isError && <p role="alert" className="text-xs text-destructive">{t("characters.voiceGeneration.historyFailed")}</p>}
            {!history.isPending && !history.isError && previews.length === 0 && (
              <div className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-5 text-center text-muted-foreground">
                <Headphones className="size-7" />
                <p className="text-sm">{t("characters.voiceGeneration.emptyHistory")}</p>
                <p className="text-xs">{t("characters.voiceGeneration.historyHint")}</p>
              </div>
            )}
            {previews.length > 0 && <fieldset className="flex max-h-60 min-w-0 flex-col gap-2 overflow-y-auto p-1" aria-label={t("characters.voiceGeneration.history")}>
              {previews.map((item, index) => {
                const selected = preview?.preview_id === item.preview_id;
                return (
                  <label key={item.preview_id} className={cn(
                    "relative flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors focus-within:ring-2 focus-within:ring-ring",
                    selected ? "border-primary/60 bg-primary/5" : "border-border bg-muted/30 hover:bg-muted/60",
                  )}>
                    <input type="radio" name="voice-preview" className="sr-only" checked={selected}
                      disabled={save.isPending} onChange={() => setSelectedId(item.preview_id)}
                      aria-label={t("characters.voiceGeneration.candidate", { number: previews.length - index })} />
                    <span aria-hidden className={cn("mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full", selected ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground")}>
                      {selected ? <Check className="size-3.5" /> : <AudioLines className="size-3.5" />}
                    </span>
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <div className="flex flex-wrap items-center justify-between gap-1 text-xs">
                        <span className="font-medium">{t("characters.voiceGeneration.candidate", { number: previews.length - index })}</span>
                        {slot.sha256 && item.sha256 === slot.sha256 && <span className="text-primary">{t("characters.voiceGeneration.current")}</span>}
                      </div>
                      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                        <span className="inline-flex items-center gap-1"><Clock3 className="size-3" />{t("characters.voiceGeneration.duration", { seconds: item.duration.toFixed(1) })}</span>
                        <span>{formatDate(item.created_at)}</span>
                      </p>
                      {item.text && <p className="line-clamp-2 break-words text-xs text-muted-foreground">{item.text}</p>}
                    </div>
                  </label>
                );
              })}
            </fieldset>}
            {preview && <div className="flex flex-col gap-2 rounded-xl border bg-muted/30 p-3">
              <p className="truncate text-xs text-muted-foreground">{preview.model || t("characters.voiceGeneration.preview")}</p>
              <audio key={preview.preview_id} src={resolveMediaUrl(preview.url) ?? undefined} controls preload="none"
                className="h-9 w-full min-w-0" aria-label={t("characters.voiceGeneration.preview")} />
            </div>}
            {previews.length > 0 && <p className="text-xs text-muted-foreground">{t("characters.voiceGeneration.historyHint")}</p>}
          </section>
        </div>
        <DialogFooter className="shrink-0 border-t px-5 py-4">
          <Button variant="outline" onClick={onClose} disabled={pending}>{t("common.cancel")}</Button>
          <Button onClick={() => void handleSave()} disabled={!preview || pending || Boolean(slot.sha256 && preview.sha256 === slot.sha256)}>
            {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
            {t(slot.path ? "characters.voiceGeneration.replace" : "characters.voiceGeneration.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
