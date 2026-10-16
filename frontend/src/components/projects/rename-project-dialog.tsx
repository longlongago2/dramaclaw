// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useState } from "react";
import { HTTPError } from "ky";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useRenameProject } from "@/lib/queries/projects";
import {
  getProjectDisplayName, getProjectNameValidationKey, normalizeProjectDisplayName,
} from "@/lib/project-name";
import type { ProjectSummary } from "@/types/project";

export function RenameProjectDialog({ project, onClose }: {
  project: ProjectSummary;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(() => getProjectDisplayName(project));
  const [serverError, setServerError] = useState<string | null>(null);
  const rename = useRenameProject(project.id);
  const normalizedName = normalizeProjectDisplayName(name);
  const errorKey = getProjectNameValidationKey(normalizedName);
  const error = serverError ?? (errorKey ? t(errorKey) : null);

  const submit = async () => {
    if (error || rename.isPending) return;
    try {
      await rename.mutateAsync(normalizedName);
      toast.success(t("project.toasts.renamed"));
      onClose();
    } catch (cause) {
      if (cause instanceof HTTPError && cause.response.status === 409) {
        setServerError(t("project.nameExistsActive"));
      } else {
        toast.error(t("project.toasts.renameFailed"));
      }
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !rename.isPending) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <DialogHeader>
            <DialogTitle>{t("project.actions.rename")}</DialogTitle>
            <DialogDescription>{t("project.renameDescription")}</DialogDescription>
          </DialogHeader>
          <div className="my-4 flex flex-col gap-2">
            <label htmlFor="rename-project-name" className="text-sm font-medium">
              {t("project.name")}
            </label>
            <Input
              id="rename-project-name"
              value={name}
              onChange={(event) => { setName(event.target.value); setServerError(null); }}
              aria-invalid={!!error || undefined}
              aria-describedby={error ? "rename-project-error" : undefined}
              disabled={rename.isPending}
              autoFocus
            />
            {error && <p id="rename-project-error" className="text-xs text-destructive">{error}</p>}
            <p className="text-xs text-muted-foreground">
              {t("project.folderName")}: <span className="break-all font-mono">{project.name}</span>
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={rename.isPending}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!!error || rename.isPending || normalizedName === getProjectDisplayName(project)}>
              {rename.isPending && <Loader2 className="size-4 animate-spin" />}
              {t("common.confirm")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
