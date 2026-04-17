# 变更：调整智能评分输入内容

## 为什么
当前智能评分输入除 `ground_truth` 与 `model_output` 外，还会带入任务 `prompt` 和评测集 `custom_tags`。你现在希望评分仅围绕标注结果、模型输出和评分标准本身进行判断，同时继续统一由大模型输出 `recall`、`accuracy` 和 `reason`。

## 变更内容
- 智能评分输入改为仅包含以下三项：
  - `ground_truth`
  - `model_output`
  - `评分标准`
- 移除评分阶段对任务 `prompt` 和评测集 `custom_tags` 的传入
- 保持 `recall`、`accuracy`、`reason` 继续由大模型统一生成
- 保持评分模型与前端展示不变

## 影响
- 受影响规范：task-management（修改）
- 受影响代码：
  - 后端：任务评分接口输入组装逻辑
  - 后端：Ark 客户端 `score_result()` 提示词模板
  - 前端：无结构变化，仅复用现有按钮与结果表
