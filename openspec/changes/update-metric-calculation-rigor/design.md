## 上下文
当前系统对单条结果的 `recall` 和 `accuracy` 采用“大模型直接打分”的方式，后端只负责解析 `0-100` 数值并落库。该方式实现简单，但存在三个核心问题：

1. 指标定义不完整：没有明确“一个命中项到底是什么”，也没有定义部分命中、重复命中、空样本和不可评测样本如何处理。
2. 聚合方式偏弱：任务级 `avg_recall` 和 `avg_accuracy` 直接对样本均值求平均，没有区分宏平均和微平均。
3. 语义容易混淆：现有 `accuracy` 字段在产品语义上接近“预测准确率”，统计定义更接近 `precision`，但未被明确说明。

## 目标
- 让单条评分可解释、可追溯、可复现
- 让任务级指标能正确反映不同复杂度样本的整体表现
- 在不破坏现有接口可用性的前提下，降低 `accuracy` 语义歧义

## 非目标
- 不在本次提案中重做模型推理流程
- 不要求所有数据类型都完全脱离大模型解析
- 不一次性移除现有 `accuracy` 字段

## 决策
### 1. 统一可评测单元
系统必须先将 `ground_truth` 和 `model_output` 标准化为“可评测单元”列表，再进入评分计算。可评测单元建议采用统一结构：

```json
{
  "type": "event",
  "key": "person-fall",
  "subject": "person",
  "action": "fall",
  "time_range": "",
  "location": "",
  "attributes": {
    "count": 1,
    "severity": "high"
  }
}
```

设计原则：
- 对结构化 JSON 优先按字段解析，不再直接让模型输出总分
- 对文本结果，允许先由大模型抽取为标准化单元，但最终分数必须由系统公式计算
- 每个单元必须具备稳定主键 `key` 或可比较的主属性组合，以支持一对一匹配

### 2. 两阶段评分流水线
单条评分改为两个阶段：

1. 标准化阶段：
   - 解析 `ground_truth`
   - 解析 `model_output`
   - 记录解析状态：`parsed`、`fallback_parsed`、`unscorable`

2. 计算阶段：
   - 对标准化后的单元执行一对一匹配
   - 匹配优先级为：主键精确匹配 > 必填属性匹配 > 可选属性相似度阈值匹配
   - 同一预测单元最多命中一个真值单元，避免重复预测重复计分

匹配产物：
- `TP`：成功匹配的真值单元数
- `FN`：未被命中的真值单元数
- `FP`：未命中任何真值的预测单元数

单条指标公式：
- `recall = TP / (TP + FN) * 100`
- `accuracy = TP / (TP + FP) * 100`

说明：
- 上述 `accuracy` 为兼容现有产品字段名称，统计学定义更接近 `precision`
- 可选新增 `precision` 别名字段，并让前端文案展示为“准确率（精确率）”
- 可选新增 `f1 = 2 * recall * accuracy / (recall + accuracy)`，用于排序和总览

### 3. 空样本与不可评测样本
为了避免指标被大量空样本稀释，需要单独定义：

- `empty sample`：`ground_truth` 与 `model_output` 归一化后都没有可评测单元
- `unscorable sample`：任一侧解析失败，无法稳定比较

处理规则：
- `empty sample` 不参与 `micro/macro recall` 与 `micro/macro accuracy` 聚合，单独统计 `empty_sample_pass_rate`
- `unscorable sample` 不参与主指标聚合，单独统计 `coverage_rate` 与 `unscorable_count`
- 当 `ground_truth` 为空但 `model_output` 非空时，记为纯 `FP` 场景，`accuracy = 0`

### 4. 任务级聚合口径
任务级不能只保留简单平均，必须至少提供以下口径：

- `micro_recall = sum(TP) / (sum(TP) + sum(FN)) * 100`
- `micro_accuracy = sum(TP) / (sum(TP) + sum(FP)) * 100`
- `macro_recall = mean(sample_recall)`
- `macro_accuracy = mean(sample_accuracy)`
- `coverage_rate = scorable_sample_count / total_sample_count * 100`
- `empty_sample_pass_rate = empty_and_correct_count / empty_sample_count * 100`

默认展示建议：
- 任务详情页优先展示 `micro_recall` 与 `micro_accuracy`
- 任务列表页和对比页展示 `micro` 口径，并提供 `macro` 作为补充说明或悬浮提示

### 5. 结果可追溯性
系统应保存或可重建以下中间结果：
- 标准化后的 GT 单元数与预测单元数
- 单条 `TP/FN/FP`
- 评分版本号，例如 `metric_version=v2`
- 命中摘要，便于前端展示“命中哪些项、漏掉哪些项、误报哪些项”

## 风险 / 权衡
- 引入标准化和匹配规则后，实现复杂度高于直接让大模型打分
- 若标准化过度依赖大模型抽取，仍然存在一定波动，因此需要固定提示词、固定 schema 和版本号
- 若直接把前端“准确率”改名为“精确率”，会影响历史认知，因此建议先兼容文案过渡

## 迁移计划
1. 保留现有 `recall` / `accuracy` 字段，新增内部 `metric_version`
2. 新任务默认按新口径计算，历史结果可按需重算
3. 前端先展示“准确率（精确率）”或增加提示说明
4. 当新口径稳定后，再评估是否对外暴露独立 `precision` / `f1`

## 待决问题
- 不同数据集是否需要可配置的“主键字段”和“匹配阈值”
- 文本型开放问答样本是否需要单独的语义单元拆分策略
- 前端是否立即展示 `f1` 与 `coverage_rate`
