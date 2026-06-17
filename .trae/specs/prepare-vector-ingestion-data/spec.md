# 向量库入库数据整理脚本 Spec

## Why
向量库入库前需要一份结构稳定、可复用的英文标注数据文件，来源为本项目 `/datasets/7` 评测集的标注结果。通过脚本化整理可以避免手工复制和翻译带来的格式错误、漏数和不可复现问题。

## What Changes
- 新增一个后端脚本，从数据库读取评测集 `7` 的评测数据及其标注结果。
- 脚本解析每条标注结果中的 JSON 内容，并将 JSON 中所有中文文本翻译为英文。
- 翻译后 SHALL 保持原 JSON 的字段名、数组、对象层级和非中文值格式不变。
- 脚本输出一个 JSON 文件，包含 `215` 条数据的翻译结果。
- 脚本执行时提供数量校验、JSON 解析校验和输出文件校验。

## Impact
- Affected specs: vector-ingestion-data-preparation
- Affected code: `backend/scripts`、`backend/app/models`、`backend/app/core/database`、可能的翻译服务客户端配置

## ADDED Requirements
### Requirement: 从评测集 7 读取标注数据
系统 SHALL 提供脚本读取 `/datasets/7` 评测集中的评测数据和对应标注结果，并仅处理存在有效标注结果的数据。

#### Scenario: 成功读取数据
- **WHEN** 用户运行向量库入库数据整理脚本
- **THEN** 脚本 SHALL 从数据库查询 `dataset_id=7` 的评测数据
- **AND** 脚本 SHALL 读取每条评测数据关联的标注结果
- **AND** 脚本 SHALL 在处理前校验可用标注数据数量

#### Scenario: 数据数量不符合预期
- **WHEN** 可用标注数据数量不是 `215`
- **THEN** 脚本 SHALL 明确报错并停止输出正式结果文件
- **AND** 错误信息 SHALL 包含实际数量和期望数量

### Requirement: 翻译 JSON 中的中文内容
系统 SHALL 将标注结果 JSON 中的所有中文文本翻译为英文，并保持 JSON 结构和非中文字段不变。

#### Scenario: 标注结果为合法 JSON
- **WHEN** 标注结果可以解析为 JSON
- **THEN** 脚本 SHALL 递归遍历对象、数组和字符串值
- **AND** 对包含中文的字符串值执行中文到英文翻译
- **AND** 不包含中文的字符串、数字、布尔值和空值 SHALL 保持原值

#### Scenario: JSON 包含嵌套结构
- **WHEN** 标注结果包含嵌套对象或数组
- **THEN** 脚本 SHALL 保持原有字段名、字段顺序、数组顺序和嵌套层级
- **AND** 仅替换需要翻译的中文字符串值

#### Scenario: 标注结果不是合法 JSON
- **WHEN** 某条标注结果无法解析为 JSON
- **THEN** 脚本 SHALL 记录该数据 ID 和失败原因
- **AND** 脚本 SHALL 失败退出，避免生成不完整或格式不一致的正式结果

### Requirement: 输出向量库入库 JSON 文件
系统 SHALL 输出一个 JSON 文件，包含 `215` 条翻译后的数据，供后续写入 VikingDB 使用。

#### Scenario: 成功输出文件
- **WHEN** 所有 `215` 条标注数据均成功翻译
- **THEN** 脚本 SHALL 生成一个 JSON 文件
- **AND** 文件 SHALL 包含 `215` 条记录
- **AND** 每条记录 SHALL 至少包含评测数据 ID、文件名、TOS 信息、原始标注 JSON 和英文翻译后的标注 JSON

#### Scenario: 输出文件校验
- **WHEN** 脚本完成输出
- **THEN** 脚本 SHALL 重新读取输出文件并校验其为合法 JSON
- **AND** 脚本 SHALL 校验记录数量为 `215`
- **AND** 脚本 SHALL 打印输出路径和记录数量

### Requirement: 可重复执行与安全默认行为
系统 SHALL 允许用户重复运行脚本，并通过显式输出路径控制生成文件位置。

#### Scenario: 指定输出路径
- **WHEN** 用户通过参数指定输出文件路径
- **THEN** 脚本 SHALL 将结果写入该路径
- **AND** 若文件已存在，脚本 SHALL 明确提示覆盖行为或要求显式覆盖参数

#### Scenario: 翻译失败
- **WHEN** 翻译服务或翻译逻辑失败
- **THEN** 脚本 SHALL 输出失败的数据 ID、字段路径和错误原因
- **AND** 脚本 SHALL 失败退出，不生成正式结果文件

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
