# [OPEN] GIF Frame Failure

## 背景
- 目标：本地复现 `01-大哥骑电瓶车.gif` 与 `01-摄像头光线自变.gif` 的 GIF 拆帧失败问题。
- 范围：仅收集运行时证据，不修改业务逻辑。

## 当前假设
- 假设 1：原始 GIF 的 TOS 签名 URL 在本地请求时就返回非 200，导致后续无法拆帧。
- 假设 2：原始 GIF 能下载成功，但文件内容损坏或格式异常，`PIL.Image.open`/`seek` 过程中失败。
- 假设 3：GIF 可正常拆出帧，但上传帧图到 TOS 或生成帧图下载链接时失败。
- 假设 4：对象 key 或 URL 编码包含特殊字符，导致模型侧或本地下载路径解析异常。
- 假设 5：这两个 GIF 只在模型调用时报错，但本地拆帧是成功的，说明问题在外部可访问性而不是拆帧逻辑本身。

## 计划
- 找到这两个 GIF 在数据集中的对象 key / URL。
- 本地直接调用拆帧函数与基础下载逻辑复现。
- 对照日志确认是下载失败、解析失败、还是上传/URL 阶段失败。

## 结果
- 已本地复现。
- 对象 `01-大哥骑电瓶车.gif`
  - `tos_key`: `AI-IPC/VideoRetrieval&IntelligentAlert/01-大哥骑电瓶车.gif`
  - `check_object_exists`: `False`
  - 原始签名 URL 本地 `GET` 返回 `404`
  - `ArkClient.extract_gif_frames()` 返回 `0` 帧
  - `DashScopeClient.extract_gif_frames()` 返回 `0` 帧
- 对象 `01-摄像头光线自变.gif`
  - `tos_key`: `AI-IPC/VideoRetrieval&IntelligentAlert/01-摄像头光线自变.gif`
  - `check_object_exists`: `False`
  - 原始签名 URL 本地 `GET` 返回 `404`
  - `ArkClient.extract_gif_frames()` 返回 `0` 帧
  - `DashScopeClient.extract_gif_frames()` 返回 `0` 帧

## 假设结论
- 假设 1：成立。原始 GIF 的签名 URL 在本地请求时就返回非 200。
- 假设 2：否决。尚未进入 `PIL.Image.open`/`seek` 阶段。
- 假设 3：否决。尚未进入帧图上传与帧图 URL 生成阶段。
- 假设 4：暂不作为主因。虽然对象 key 中包含 `&`，但更直接的证据是对象存在性检查已返回 `False`。
- 假设 5：否决。问题并非只发生在模型侧，本地同样可复现。

## TOS / 数据库迁移痕迹
- 数据库中与 `大哥骑电瓶车` 相关的记录：
  - `01-大哥骑电瓶车.gif` -> `AI-IPC/VideoRetrieval&IntelligentAlert/01-大哥骑电瓶车.gif`
  - `16-大哥骑电瓶车.gif` -> `AI-IPC/VideoRetrieval&IntelligentAlert/16-大哥骑电瓶车.gif`
- TOS 全量模糊搜索结果：
  - 命中 `AI-IPC/VideoRetrieval&IntelligentAlert/16-大哥骑电瓶车.gif`
  - 未命中 `01-大哥骑电瓶车.gif`
- 结论：`01-大哥骑电瓶车.gif` 很可能已被替换、重命名或迁移为 `16-大哥骑电瓶车.gif`。

- 数据库中与 `摄像头光线自变` 相关的记录：
  - 仅命中 `01-摄像头光线自变.gif` -> `AI-IPC/VideoRetrieval&IntelligentAlert/01-摄像头光线自变.gif`
- TOS 全量模糊搜索结果：
  - 未命中 `摄像头光线自变`
  - 未命中 `光线自变`
  - 未命中 `摄像头光线`
- 结论：`01-摄像头光线自变.gif` 当前没有发现明确的新 key 或迁移痕迹，更像是对象已丢失。

## 已执行修复
- 已将数据库中 `01-大哥骑电瓶车.gif`（`evaluation_data.id = 1`）的 `tos_key`：
  - 从 `AI-IPC/VideoRetrieval&IntelligentAlert/01-大哥骑电瓶车.gif`
  - 更新为 `AI-IPC/VideoRetrieval&IntelligentAlert/16-大哥骑电瓶车.gif`

## 修复后验证
- 数据库回读结果：
  - `01-大哥骑电瓶车.gif` -> `AI-IPC/VideoRetrieval&IntelligentAlert/16-大哥骑电瓶车.gif`
- 修复后目标 key 的签名 URL 本地 `GET`：
  - `200 image/gif 1966523`
