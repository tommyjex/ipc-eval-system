# 火山模型评测链路新增 260628 模型 Spec

## Why
当前评测任务的火山引擎模型列表未包含 `doubao-seed-2-1-pro-260628` 和 `doubao-seed-2-1-turbo-260628`，用户无法在评测链路中选择这两个新模型。

## What Changes
- 在火山引擎模型选项中新增 `doubao-seed-2-1-pro-260628`。
- 在火山引擎模型选项中新增 `doubao-seed-2-1-turbo-260628`。
- 前端展示名称、筛选名称、任务创建提交值、后端保存与推理调用使用的模型名称必须完全一致。

## Impact
- Affected specs: 任务管理、评测任务创建、评测任务列表筛选、火山引擎推理链路
- Affected code: `frontend/src/pages/tasks/TaskListPage.tsx`、`backend/app/api/tasks.py`、`backend/app/services/ark_client.py`

## ADDED Requirements
### Requirement: 火山引擎新增模型可选
The system SHALL allow users to select `doubao-seed-2-1-pro-260628` and `doubao-seed-2-1-turbo-260628` as target models when creating Volcengine evaluation tasks.

#### Scenario: 创建任务选择新增 Pro 模型
- **WHEN** 用户在创建评测任务时选择模型供应商为火山引擎
- **THEN** 目标模型下拉列表中 SHALL include `doubao-seed-2-1-pro-260628`
- **AND** 该选项的前端显示名称 SHALL equal `doubao-seed-2-1-pro-260628`

#### Scenario: 创建任务选择新增 Turbo 模型
- **WHEN** 用户在创建评测任务时选择模型供应商为火山引擎
- **THEN** 目标模型下拉列表中 SHALL include `doubao-seed-2-1-turbo-260628`
- **AND** 该选项的前端显示名称 SHALL equal `doubao-seed-2-1-turbo-260628`

#### Scenario: 任务保存与推理使用相同模型名
- **WHEN** 用户使用任一新增模型创建评测任务
- **THEN** 后端保存的 `target_model` SHALL equal 用户选择的完整模型名称
- **AND** 推理请求传给火山引擎客户端的 `model` SHALL equal 后端保存的 `target_model`

#### Scenario: 列表展示和筛选使用相同模型名
- **WHEN** 已创建任务的 `target_model` 为任一新增模型
- **THEN** 任务列表展示的模型名称 SHALL equal 保存的 `target_model`
- **AND** 目标模型筛选项展示名称 SHALL equal 筛选提交值

## MODIFIED Requirements
### Requirement: 火山引擎模型选项
火山引擎模型选项 SHALL include existing supported models and the two new 260628 models without changing existing model names or provider behavior.

## REMOVED Requirements
无。
