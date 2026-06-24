# Tasks
- [x] Task 1: 更新大模型标注默认模型配置。
  - [x] SubTask 1.1: 将 `backend/app/core/config.py` 中 `ark_model` 默认值更新为 `doubao-seed-2-1-pro-260628`。
  - [x] SubTask 1.2: 确认 `ArkClient.default_model` 仍从 `settings.ark_model` 初始化。
- [x] Task 2: 验证 AI 标注链路使用实际模型名称。
  - [x] SubTask 2.1: 确认 `/api/ai-annotations` 未传入 `model` 时，非 GIF 标注调用使用 `settings.ark_model`。
  - [x] SubTask 2.2: 确认 `/api/ai-annotations` 未传入 `model` 时，GIF 标注调用使用 `settings.ark_model`。
  - [x] SubTask 2.3: 确认 AI 标注写入或更新 `annotations.model_name` 时记录 `model or settings.ark_model`。
  - [x] SubTask 2.4: 确认显式传入 `model` 时仍优先使用请求模型，不被默认模型覆盖。
- [x] Task 3: 运行必要验证。
  - [x] SubTask 3.1: 运行后端语法或单元测试检查，确认配置改动无导入或语法错误。
  - [x] SubTask 3.2: 运行最小行为检查，确认 `get_settings().ark_model` 默认值为 `doubao-seed-2-1-pro-260628`。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1 and Task 2.
