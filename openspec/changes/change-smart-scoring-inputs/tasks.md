## 1. 实施
- [x] 1.1 梳理当前智能评分输入中 `prompt`、`custom_tags` 与 `评分标准` 的来源
- [x] 1.2 调整评分接口，仅传入 `ground_truth`、`model_output`、`评分标准`
- [x] 1.3 更新 Ark 评分提示词模板，移除任务 prompt 和自定义标签描述，并保留大模型统一输出 `recall`、`accuracy`、`reason`

## 2. 验证
- [x] 2.1 验证点击“智能评分”后仍可正常触发评分流程
- [x] 2.2 验证评分模型输入仅包含 `ground_truth`、`model_output`、`评分标准`
- [x] 2.3 验证前端 `召回率`、`准确率`、`评分理由` 展示不受影响
