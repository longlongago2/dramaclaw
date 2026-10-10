# MrToken 供应商渠道

在「设置 → 模型与渠道 → 供应商渠道管理」中添加 **MrToken**，填写平台 API Key。
点击「获取可用模型」调用 `GET https://api.mrtoken.cn/v1/models`，以返回的
`data[].id` 原样填写功能或媒体模型映射。列表不提供能力信息；请根据平台模型说明
选择对应用途，列表为空时不会自动补充模型。保存渠道前也会调用模型发现接口验证 Key。

所有请求使用 `Authorization: Bearer <PLATFORM_API_KEY>`。渠道复用 NewAPI
的 OpenAI 兼容适配器（type 1），默认渠道地址为 `https://api.mrtoken.cn`。
直接使用 SDK 时地址为 `https://api.mrtoken.cn/v1`；渠道配置接受该写法并去掉末尾
`/v1`，防止重复路径。Key 使用现有本地渠道设置机制保存，前端重新读取配置只收到
脱敏预览。模型发现错误只返回状态码或固定消息，不透传可能包含 Key 的上游错误体。

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

渠道能力声明用于下拉框筛选，不等同于生成协议已经适配。当前实现复用
Chat Completions 和 OpenAI 风格 `/v1/images/generations`、`/v1/images/edits`。
Qwen 的 `input/parameters` 图片形态、专用视频提交与查询、音乐、3D 接口仍需
独立适配器；本次能力声明修正没有完成这些接口适配。

接口依据：[MrToken AI API 完整文档](https://www.mrtoken.cn/mrtoken/docs/ai-api/all.md)。
