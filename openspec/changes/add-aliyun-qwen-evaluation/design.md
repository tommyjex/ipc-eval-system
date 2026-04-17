# 设计：阿里云千问评测接入

## 背景
当前任务执行路径在 `_run_evaluation_task()` 中无条件使用 `ArkClient`，即便任务的 `model_provider` 被设置为 `aliyun`，实际也不会走阿里百炼接口。这意味着前端供应商选项与后端执行链路不一致。

## 目标
- 让评测任务按 `model_provider` 选择正确的模型调用实现
- 为阿里云千问接入文本、图片、视频三类输入
- 保持现有火山引擎路径稳定，不影响已存在的评测能力

## 方案概述
### 1. 增加模型供应商抽象
为任务执行引入统一的推理客户端接口，例如：
- `build_annotation_content()`
- `annotate()`
- `annotate_gif()`

第一阶段保留现有 `ArkClient`，新增 `DashScopeClient`，并通过一个工厂函数按 `model_provider` 返回对应客户端。

### 2. 阿里百炼调用策略
阿里百炼 DashScope 支持：
- 纯文本模型接口：`POST /api/v1/services/aigc/text-generation/generation`
- 多模态模型接口：`POST /api/v1/services/aigc/multimodal-generation/generation`

默认中国站基础地址可配置为：
- `https://dashscope.aliyuncs.com/api/v1`

认证方式：
- `Authorization: Bearer $DASHSCOPE_API_KEY`

### 3. 输入类型处理
- 文本：仅发送 prompt 文本到文本生成接口
- 图片：发送图片 URL 与文本提示到多模态接口
- 视频：发送视频 URL 与文本提示到多模态接口
- GIF：沿用当前抽帧策略，转换为多张图片 URL 后发送到多模态接口

媒体 URL 继续复用现有 TOS 签名下载地址。

### 4. 任务执行分流
在 `_run_evaluation_task()` 中根据 `task.model_provider` 分流：
- `volcengine` -> `ArkClient`
- `aliyun` -> `DashScopeClient`

如果供应商未实现，任务结果应写入失败原因，避免静默回退到错误供应商。

### 5. 模型选择与兼容性
前端阿里千问模型列表需要至少覆盖：
- 文本模型：`qwen-plus`
- 多模态模型：`qwen-vl-plus`、`qwen-vl-max`、`qwen3.6-plus`

第一阶段不强制做“模型类型与数据类型”的前端校验，但后端必须在调用失败时返回清晰错误原因。

### 6. 配置项
新增后端配置项：
- `dashscope_api_key`
- `dashscope_base_url`，默认 `https://dashscope.aliyuncs.com/api/v1`

## 风险与权衡
- 阿里百炼不同模型对视频/图片支持能力不同，第一阶段通过“可选模型列表 + 清晰错误回写”控制风险
- 多模态接口请求体格式与方舟不同，因此不建议直接在 `ArkClient` 中混写供应商逻辑，拆出独立客户端更易维护
- GIF 抽帧会带来额外请求，但现有策略已被验证可用，优先复用
