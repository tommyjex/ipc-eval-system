# Tasks
- [x] Task 1: 更新火山引擎模型选项，新增两个 260628 模型。
  - [x] SubTask 1.1: 在评测任务创建页的火山引擎模型列表中加入 `doubao-seed-2-1-pro-260628`。
  - [x] SubTask 1.2: 在评测任务创建页的火山引擎模型列表中加入 `doubao-seed-2-1-turbo-260628`。
  - [x] SubTask 1.3: 确认两个选项的 `value` 与 `label` 完全相同。
- [x] Task 2: 验证新增模型在评测链路中的名称传递一致。
  - [x] SubTask 2.1: 确认创建任务请求提交的 `target_model` 为用户选择的完整模型名称。
  - [x] SubTask 2.2: 确认任务列表展示和目标模型筛选使用同一套模型名称。
  - [x] SubTask 2.3: 确认后端推理调用直接使用任务保存的 `target_model`，不做名称映射或改写。
- [x] Task 3: 运行必要验证。
  - [x] SubTask 3.1: 运行前端类型检查或构建，确认模型列表变更无编译错误。
  - [x] SubTask 3.2: 运行相关后端测试或最小检查，确认评测任务模型字段兼容新增名称。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1 and Task 2.
