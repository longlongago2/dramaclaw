// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useTranslation } from 'react-i18next';
import { useId } from 'react';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { STICKMAN_THEME_GROUPS, concreteStickmanTheme, stickmanThemeGroup } from '@/lib/stickman-themes';

const THEME_LABEL_KEYS: Record<string, string> = {
  classic: 'styles.themeClassic', modern: 'styles.themeModern', prehistoric: 'styles.themePrehistoric',
};
const PRESET_DEFAULT = '__preset_default__';
const VARIANT_LABEL_KEYS: Record<string, string> = {
  '1a': 'styles.theme1A', '1b': 'styles.theme1B',
  '2a': 'styles.theme2A', '2b': 'styles.theme2B',
};

export function StyleThemeSelect({ options, value, onChange, disabled = false }: {
  options?: readonly string[]; value: string | null;
  onChange: (theme: string | null) => void; disabled?: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  if (!options?.length) return null;
  const group = stickmanThemeGroup(value);
  const concrete = concreteStickmanTheme(value);
  const variants = group ? STICKMAN_THEME_GROUPS[group as keyof typeof STICKMAN_THEME_GROUPS] : [];
  const items = [
    { value: PRESET_DEFAULT, label: t('styles.themeDefault') },
    ...Object.keys(STICKMAN_THEME_GROUPS).filter((key) => options.includes(key)).map((theme) => ({ value: theme, label: t(THEME_LABEL_KEYS[theme]) })),
  ];
  return (
    <div className="flex min-w-0 flex-col gap-2 text-xs text-muted-foreground">
      <Label id={`${id}-label`} htmlFor={id} className="text-xs text-muted-foreground">{t('styles.themeLabel')}</Label>
      <Select items={items} value={group ?? PRESET_DEFAULT}
        onValueChange={(next) => onChange(next === PRESET_DEFAULT ? null : concreteStickmanTheme(next))} disabled={disabled}>
        <SelectTrigger id={id} aria-labelledby={`${id}-label`} aria-describedby={`${id}-hint`}
          className="!h-9 w-full rounded-[8px] border-white/10 bg-white/[0.025] px-3 text-sm shadow-none focus-visible:border-white/20 focus-visible:ring-2 focus-visible:ring-white/8 dark:bg-white/[0.025]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent sideOffset={8} alignItemWithTrigger={false}
          className="rounded-md p-1 shadow-xl shadow-black/20 [&_[data-slot=select-item]]:min-h-8 [&_[data-slot=select-item]]:rounded-sm [&_[data-slot=select-item]]:px-2 [&_[data-slot=select-item]]:py-1.5 [&_[data-slot=select-item]]:text-xs [&_[data-slot=select-item]:focus]:bg-white/8 [&_[data-slot=select-item]:focus]:text-current [&_[data-slot=select-item]_svg]:size-3.5">
          {items.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
        </SelectContent>
      </Select>
      {variants.length > 1 ? (
        <>
          <Label id={`${id}-variant-label`} htmlFor={`${id}-variant`} className="text-xs text-muted-foreground">{t('styles.themeVariantLabel')}</Label>
          <Select items={variants.map((variant) => ({ value: variant, label: t(VARIANT_LABEL_KEYS[variant]) }))}
            value={concrete} onValueChange={onChange} disabled={disabled}>
            <SelectTrigger id={`${id}-variant`} aria-labelledby={`${id}-variant-label`}
              className="!h-9 w-full rounded-[8px] border-white/10 bg-white/[0.025] px-3 text-sm shadow-none focus-visible:border-white/20 focus-visible:ring-2 focus-visible:ring-white/8 dark:bg-white/[0.025]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent sideOffset={8} alignItemWithTrigger={false}>
              {variants.map((variant) => <SelectItem key={variant} value={variant}>{t(VARIANT_LABEL_KEYS[variant])}</SelectItem>)}
            </SelectContent>
          </Select>
        </>
      ) : null}
      <p id={`${id}-hint`} className="text-xs leading-4 text-muted-foreground">{t('styles.themeHint')}</p>
    </div>
  );
}
