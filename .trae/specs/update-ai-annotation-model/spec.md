# 大模型标注默认模型更新 Spec

## Why
当前大模型标注链路在未显式传入模型时使用旧的 `ark_model` 默认值，不能满足将模型标注统一迁移到 `doubao-seed-2-1-pro-260628` 的需求。

## What Changes
- 将大模型标注链路的默认模型更新为 `doubao-seed-2-1-pro-260628`。
- 未显式传入 `model` 的 AI 标注请求应使用新的默认模型发起火山引擎请求。
- AI 标注结果写入 `annotations.model_name` 时应记录实际使用的模型名称 `doubao-seed-2-1-pro-260628`。
- 保持显式传入 `model` 的请求行为不变：如果请求指定模型，则继续优先使用请求模型。

## Impact
- Affected specs: 数据标注、大模型标注、火山引擎默认模型配置
- Affected code: `backend/app/core/config.py`、`backend/app/api/annotations.py`、`backend/app/services/ark_client.py`

## ADDED Requirements
### Requirement: 大模型标注使用新的默认模型
The system SHALL use `doubao-seed-2-1-pro-260628` as the default AI annotation model when an AI annotation request does not provide a `model`.

#### Scenario: 未传入模型时执行 AI 标注
- **WHEN** 用户发起 `/api/ai-annotations` 请求且请求体未提供 `model`
- **THEN** 系统 SHALL call 火山引擎标注接口 with model `doubao-seed-2-1-pro-260628`
- **AND** 标注结果 SHALL save `annotations.model_name` as `doubao-seed-2-1-pro-260628`

#### Scenario: GIF 数据未传入模型时执行 AI 标注
- **WHEN** 用户对 GIF 数据发起 AI 标注且请求体未提供 `model`
- **THEN** 系统 SHALL call GIF 标注链路 with model `doubao-seed-2-1-pro-260628`
- **AND** 标注结果 SHALL save `annotations.model_name` as `doubao-seed-2-1-pro-260628`

#### Scenario: 显式传入模型时执行 AI 标注
- **WHEN** 用户发起 `/api/ai-annotations` 请求且请求体提供了 `model`
- **THEN** 系统 SHALL continue to use the provided `model`
- **AND** 标注结果 SHALL save `annotations.model_name` as the provided `model`

## MODIFIED Requirements
### Requirement: 火山引擎默认模型配置
火山引擎默认模型配置 SHALL default to `doubao-seed-2-1-pro-260628` for code paths that rely on `settings.ark_model`, including AI annotation and Ark client default model initialization.

## REMOVED Requirements
无。
