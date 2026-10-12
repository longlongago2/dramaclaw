# MrToken 供应商渠道

先在进程环境中设置 `PLATFORM_API_KEY`，然后运行
`uv run python scripts/check_mrtoken.py` 查询可用模型。脚本首先调用
`GET https://api.mrtoken.cn/v1/models`，只输出模型 ID 和数量，不保存密钥，
不创建收费生成任务。不要把真实密钥写入命令参数、仓库文件或聊天回复。
缺少密钥时退出码为 2，查询失败为 1，成功为 0；空列表不会补充默认模型。
此环境变量仅用于检查脚本；CE 运行配置仍通过下方渠道管理保存。
也可以运行 `uv run python scripts/check_mrtoken.py --key-file "外部密钥文件.json"`，
从仓库外的 JSON 文件读取 `key` 字段。文件中的 URL 不会覆盖平台地址，
密钥只用于本次请求，脚本不会复制密钥文件或将密钥写入 CE 配置。

在「设置 → 模型与渠道 → 供应商渠道管理」中添加 **MrToken**，填写平台 API Key。
点击「获取可用模型」调用 `GET https://api.mrtoken.cn/v1/models`，以返回的
`data[].id` 原样填写功能或媒体模型映射。列表不提供能力信息；请根据平台模型说明
选择对应用途，列表为空时不会自动补充模型。保存渠道前也会调用模型发现接口验证 Key。

所有请求使用 `Authorization: Bearer <PLATFORM_API_KEY>`。渠道复用 NewAPI
的 OpenAI 兼容适配器（type 1），默认渠道地址为 `https://api.mrtoken.cn`。
直接使用 SDK 时地址为 `https://api.mrtoken.cn/v1`；渠道配置接受该写法并去掉末尾
`/v1`，防止重复路径。Key 使用现有本地渠道设置机制保存，前端重新读取配置只收到
脱敏预览。模型发现错误按文档优先读取 `detail.reasons`、`error.message`、
`detail` 字符串和 `message`，去除完整密钥后输出有限长度的说明，不透传原始错误体。

渠道能力按 2026-10-09 使用当前平台 Key 返回的 100 个模型，以及平台文档判断：

| 能力 | 模型示例与依据 |
| --- | --- |
| text | DeepSeek、Qwen、GPT 等对话模型 |
| vision | Gemini 等多模态模型；由模型家族推断，需以具体模型说明为准 |
| image | `gpt-image-2`、`qwen-image-2.1`、`longcat-image` |
| video | `doubao-seedance-2.5`、`wan3.0-video`、HappyHorse、MiniMax 视频模型 |
| audio | `minimax-music-3`、`yue2-music`、`yue2-music-cover`；音乐生成和翻唱，不代表 TTS |

模型列表仅含 `id/model/object/created`，没有逐模型能力字段，因此分类依据是模型
名称与文档，并非接口返回的能力标签。当前 Key 未列出 Embedding 或 Rerank 模型，
渠道不声明这两类能力。列表还含 `hunyuan3d-v2.1`、`trellis2` 等 3D 模型，但现有
渠道能力枚举没有 3D，不将其归入图片或视频。模型 ID 保留平台返回值，不自动添加前缀。

渠道能力声明用于下拉框筛选，不等同于所有生成协议已经适配。当前实现复用
Chat Completions 和 OpenAI 风格 `/v1/images/generations`、`/v1/images/edits`。
Qwen 的 `input/parameters` 图片形态、H3/Seedance 2.0 以外的视频模型、音乐和 3D 接口仍需适配。

## MiniMax H3 视频

需要同时更新并重启相邻的 `dramaclaw-gateway` 源码构建。MrToken 渠道仍使用
type 1 和 `https://api.mrtoken.cn`，网关按照平台地址自动选用 H3 视频适配器。
现成的媒体模型配置见 [H3 模型配置示例](../examples/mrtoken-h3-media-models.json)。
在高级配置中选择 MrToken 渠道、填写示例中的模型 ID 和对应 config，再保存媒体模型。
示例也可作为 `/model-gateway/custom/newapi/media-models` 的请求体；该接口保存完整
媒体模型列表，使用前需合并已有模型，避免覆盖原来的映射。示例不包含凭据。

H3 R2V 的本地默认档位为 720p、16:9：请求 1280×720 会向上对齐为 1280×736。
未传尺寸时也使用 1280×736；支持 1–4 张图片参考和 1–30 秒时长，不接受首尾帧
或视频/音频参考。目录明确声明 H3 不生成原生音频。

支持 `minimax-h3-t2v`（文生）、`minimax-h3-i2v`（文生/首帧/首尾帧）、
`minimax-h3-r2v`（1–4 张参考图），以及 MAX T2V / I2V。MAX I2V 必填首帧。
时长为 1–30 秒，图片通过平台上传接口转换成 file ID；尺寸向上对齐到 32 的倍数，
每边不超过 2048。图片输入支持 URL、Base64 data URL 或本 Key 的 file ID。
H3 本地图片直接转换为 Base64 交给网关上传至平台，不依赖公共媒体中转。
外部图片 URL 继续执行 SSRF 校验；本地图片限制 PNG/JPEG/WebP、单张最多 20 MiB。

创建接受 HTTP 202，查询和下载携带创建时的平台模型 ID。任务保存在现有网关数据库，
结果通过网关签名下载代理和 DramaClaw 归档链交付，下载器无需额外的登录令牌。
提交出现连接异常时不会自动重复创建。
平台真实测试已完成 H3 T2V 的提交、轮询和 MP4 下载；其余模式已通过契约转换测试。
需配置本地网关模型价格；平台可能按实际生成时长计费，实际时长可能略长于请求时长。

## Seedance 2.0

同一 MrToken 渠道支持 `doubao-seedance-2.0`、`doubao-seedance-2.0-fast`、
`doubao-seedance-2.0-mini`，配置见
[Seedance 2.0 媒体目录示例](../examples/mrtoken-seedance2-media-models.json)。
三个型号走 Seedance 专用提交/查询接口，不能只沿用通用 OpenAI/Sora 视频协议。
支持文生、首帧、首尾帧、图片参考和图/视频/音频参考，固定时长 4–15 秒。
Fast/Mini 为 480p、720p；基础型号的 1080p 仅适用于文生/首帧输入。
参考图上限 9，视频和音频各 3，合计最多 12；参考音频不能单独生成。

通过现有媒体中转配置提供供应商可访问的 URL。网关把标准 DC-Media 输入转换为
原生 content 数组，保存平台任务 ID，成功后读取 content.video_url 归档。
平台模型名不会改成火山引擎带日期的模型名；Seedance 不调用 H3 文件接口。

可复用配置流程见 [mrtoken-integration skill](../skills/mrtoken-integration/SKILL.md)，
附有独立的只读模型发现脚本、协议说明及不含凭据的合并配置。

2026-10-12 本机验证：H3 R2V 使用一张本地参考图、请求 1 秒，实际输出
1280×736、1.625 秒、24 fps 的 H.264 视频，提交、查询、归档和浏览器播放均通过。
四图输入由契约测试覆盖。Seedance 三个型号均能在模型发现中列出，但真实创建
返回上游“模型不存在或无权访问”，未产生可验证的视频；需 MrToken 侧检查权限
或模型映射。配置和协议转换测试已完成，此限制不应被描述为真实生成通过。

接口依据：[MrToken AI API 完整文档](https://www.mrtoken.cn/mrtoken/docs/ai-api/all.md)。
