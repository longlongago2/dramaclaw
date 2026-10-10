# 本地风格图片

全部 45 套风格封面合并到一张 `covers-<hash>.webp`，每套风格的四张人物示例
合并到一张 `<style>-<hash>.webp`。逻辑路径与提示词仍由
`src/novelvideo/freezone/style_templates.json` 决定，像素区域映射在
`frontend/public/style-gallery/styleSprites.json`。

图片依据清单中的风格提示词通过内置 image_gen 生成。封面每格 384×216，
人物示例每格 384×512；统一以质量 65 编码为 WebP。
生成提示词、工具参数、源图片和文件校验值保存在
`resources/style-gallery/style-gallery-originals-20261010.zip` 的 `manifest.json` 中。

坐标映射与雪碧图一起维护；组件在构建时导入 JSON，无需额外异步请求。
Vite 将 public 文件复制到 dist，Web Docker 镜像随之包含这些资源。
默认无需配置图片 CDN；配置 `STYLE_GALLERY_ASSET_BASE` 时保留外部独立图片模式。

维护脚本已收进原始资源压缩包，不参与系统业务或部署。
需要重新生成或替换图片时，先解压资源包，再按
`resources/style-gallery/README.md` 的说明重建并替换本目录的图片与映射。
原始 PNG 和打包中间文件单独归档保存；发布只需本目录的 46 张雪碧图与坐标映射。
