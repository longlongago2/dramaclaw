// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab

/**
 * 风格图片地址的唯一解析点。
 *
 * 默认使用随包发布的同源 /style-gallery/ 图片。后端配置
 * STYLE_GALLERY_ASSET_BASE 时由接口下发 OSS/CDN 前缀,这里直接拼。
 */
export function resolveStyleAssetUrl(rel: string, assetBase: string): string {
  if (!rel) return '';
  if (!assetBase) return `/style-gallery/${rel}`;
  return `${assetBase.replace(/\/+$/, '')}/${rel}`;
}
