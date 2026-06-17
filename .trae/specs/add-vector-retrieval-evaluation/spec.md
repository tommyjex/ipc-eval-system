# 向量检索效果评估模块 Spec

## Why
当前平台已经支持摄像头场景数据集管理、模型评测和智能评分，但缺少对向量检索链路效果的系统化评估能力。新增该模块后，用户可以基于已有数据集配置 VikingDB 多模态检索，观察 search、rerank 和截断后的结果质量。

## What Changes
- 新增向量检索效果评估入口，支持从已有数据集中选择评估数据。
- 前端提供配置表单，包含数据集选择、`top_k` 设置和标量过滤字段填写。
- 前端提供搜索结果展示页，展示原始检索、rerank 后排序和截断后保留结果。
- 后端接入 BytePlus VikingDB `search_by_multi_modal` 能力，依赖安装方式为 `python3 -m pip install -U vikingdb-python-sdk`。
- 后端接入 BytePlus Rerank 接口，对检索结果进行二次排序。
- 后端检索链路固定为 `search -> rerank -> 截断`，截断策略包含低分截断和 step delta 截断。
- 追加迭代：前端评测数据集下拉框改为使用 VikingDB Collection 列表接口返回的数据集。
- 追加迭代：前端增加文字 query 输入框，支持基于文本 query 发起检索。
- 追加迭代：标量过滤输入从 JSON 文本框调整为“输入文字回车生成标签”的交互，标签不可编辑、仅可删除。
- 追加迭代：“提交评估”按钮文案改为“检索”。
- 追加迭代：前端在用户选择 VikingDB Collection 后查询该 Collection 的 Index 列表，并提供 Index 筛选框供用户选择。
- 追加迭代：调整检索配置区布局，将“检索”按钮移动到标量过滤标签输入区域下方。
- 追加迭代：优化 Search、Rerank 和最终结果列表字段展示，移除不必要列，并将元数据直接展示为易读文本。
- 追加迭代：前端增加低分截断阈值和 step delta 阈值输入框，提交时覆盖后端默认截断配置。
- 追加迭代：Search 原始结果、Rerank 排序结果、截断后最终结果三个列表增加分页，每页最多展示 10 条。
- 追加迭代：向量检索结果页支持鼠标左键双击标记特定数据条目，按该条目是否进入最终结果同步高亮三个列表。

## Impact
- Affected specs: vector-retrieval-evaluation
- Affected code: `backend/app/api`、`backend/app/services`、`backend/app/core/config`、`frontend/src/api/index.ts`、`frontend/src/pages`

## ADDED Requirements
### Requirement: 向量检索评估配置
系统 SHALL 提供向量检索评估配置页面，允许用户选择已有数据集、设置检索数量 `top_k`，并填写传给 VikingDB 的标量过滤字段。

#### Scenario: 用户配置检索评估参数
- **WHEN** 用户打开向量检索评估页面
- **THEN** 页面展示数据集选择、`top_k` 输入和标量过滤字段输入控件
- **AND** 数据集选择项 SHALL 使用当前系统已有数据集列表

#### Scenario: 用户填写标量过滤字段
- **WHEN** 用户填写标量过滤字段
- **THEN** 系统 SHALL 支持以 JSON 格式提交过滤条件
- **AND** JSON 解析失败时 SHALL 在前端阻止提交并展示错误提示

#### Scenario: 用户提交检索评估
- **WHEN** 用户选择数据集并提交检索评估
- **THEN** 前端 SHALL 调用后端检索评估接口
- **AND** 请求 SHALL 包含数据集 ID、`top_k` 和标量过滤条件

### Requirement: VikingDB 多模态检索
系统 SHALL 在后端通过 BytePlus VikingDB SDK 调用 `search_by_multi_modal` 完成多模态检索，支持基于数据集样本的图片或视频对象 URL 发起检索。

#### Scenario: 后端发起 VikingDB 检索
- **WHEN** 后端收到向量检索评估请求
- **THEN** 后端 SHALL 根据数据集样本构造 VikingDB 多模态检索请求
- **AND** 请求 SHALL 传入 `limit=top_k`
- **AND** 若用户提供标量过滤条件，后端 SHALL 将其映射为 VikingDB `filter` 参数

#### Scenario: VikingDB 配置缺失
- **WHEN** VikingDB 必要配置或鉴权信息缺失
- **THEN** 后端 SHALL 返回明确错误信息
- **AND** 前端 SHALL 展示接口失败提示

### Requirement: Rerank 二次排序
系统 SHALL 在 VikingDB 检索完成后调用 BytePlus Rerank 接口，对 search 返回结果进行二次排序。

#### Scenario: search 结果进入 rerank
- **WHEN** VikingDB 返回候选结果
- **THEN** 后端 SHALL 将候选结果转换为 Rerank 请求数据
- **AND** Rerank 返回的分数 SHALL 与候选结果一一对应
- **AND** 后端 SHALL 按 Rerank 分数从高到低排序

#### Scenario: rerank 调用失败
- **WHEN** Rerank 接口调用失败
- **THEN** 后端 SHALL 返回失败原因
- **AND** 不得返回未经标识的伪成功结果

### Requirement: 检索结果截断
系统 SHALL 在 rerank 排序后执行截断策略，支持低分截断和 step delta 截断，并返回截断原因。

#### Scenario: 低分截断
- **WHEN** rerank 后结果分数低于配置的最低分阈值
- **THEN** 后端 SHALL 将该结果及其后续低置信结果从最终结果中截断
- **AND** 响应 SHALL 标记截断原因包含低分阈值

#### Scenario: step delta 截断
- **WHEN** 相邻 rerank 分数差值达到配置的 step delta 阈值
- **THEN** 后端 SHALL 从分数断崖处截断后续结果
- **AND** 响应 SHALL 标记截断原因包含 step delta

#### Scenario: 无需截断
- **WHEN** 所有 rerank 结果均未触发截断策略
- **THEN** 后端 SHALL 返回全部 rerank 后结果
- **AND** 响应 SHALL 标记未触发截断

### Requirement: 搜索结果展示页
系统 SHALL 提供向量检索搜索结果展示页，展示 search 原始结果、rerank 后结果和截断后最终结果。

#### Scenario: 展示检索评估结果
- **WHEN** 检索评估请求成功完成
- **THEN** 前端 SHALL 展示每条结果的对象名称、预览信息、原始检索分数、rerank 分数和是否被截断
- **AND** 前端 SHALL 明确区分 search、rerank、最终保留结果

#### Scenario: 无结果
- **WHEN** 检索链路返回空结果
- **THEN** 前端 SHALL 展示空态提示
- **AND** 不得展示错误状态

#### Scenario: 接口失败
- **WHEN** 检索评估接口失败
- **THEN** 前端 SHALL 展示错误提示
- **AND** 提供重新提交入口

## MODIFIED Requirements
### Requirement: 向量检索评估配置
系统 SHALL 提供向量检索配置页面，允许用户从 VikingDB Collection 列表选择检索数据集，基于选中 Collection 查询并选择 VikingDB Index，输入文字 query，设置检索数量 `top_k`，配置低分截断阈值和 step delta 阈值，并通过标签化输入控件填写标量过滤条件。

#### Scenario: 用户选择 VikingDB 数据集
- **WHEN** 用户打开向量检索评估页面
- **THEN** 前端 SHALL 调用后端接口获取 VikingDB Collection 列表
- **AND** 后端 SHALL 参考 BytePlus VikingDB `listVikingdbCollection` 接口查询 Collection
- **AND** 数据集下拉框 SHALL 展示 VikingDB Collection 名称
- **AND** 页面 SHALL 不再使用本项目业务评测集列表作为该下拉框的数据源

#### Scenario: 用户选择 VikingDB Index
- **WHEN** 用户选择一个 VikingDB Collection
- **THEN** 前端 SHALL 调用后端接口查询该 Collection 下的 Index 列表
- **AND** 后端 SHALL 参考 BytePlus VikingDB `ListVikingdbIndex` 接口查询 Index
- **AND** 前端 SHALL 展示 Index 筛选框供用户选择
- **AND** 若该 Collection 存在多个 Index，用户 SHALL 可以在筛选框中切换
- **AND** 检索请求 SHALL 包含用户选择的 Index 名称

#### Scenario: Collection 变更后刷新 Index
- **WHEN** 用户从一个 Collection 切换到另一个 Collection
- **THEN** 前端 SHALL 重新查询新 Collection 的 Index 列表
- **AND** 前端 SHALL 清空或替换旧 Collection 的 Index 选择
- **AND** 若新 Collection 无可用 Index，前端 SHALL 阻止检索并提示用户

#### Scenario: 用户输入文字 query
- **WHEN** 用户在搜索框输入文字 query
- **THEN** 前端 SHALL 将该 query 提交给后端检索接口
- **AND** 后端 SHALL 使用文字 query 构造 VikingDB 多模态检索请求
- **AND** query 为空时前端 SHALL 阻止提交并提示用户输入搜索内容

#### Scenario: 用户填写标量过滤标签
- **WHEN** 用户在标量过滤输入框输入文字并按回车
- **THEN** 前端 SHALL 将输入内容转换为一个不可编辑标签
- **AND** 用户 SHALL 可以删除已有标签
- **AND** 用户 SHALL 可以输入多个标签
- **AND** 前端 SHALL 将标签列表提交给后端作为标量过滤条件

#### Scenario: 用户配置截断阈值
- **WHEN** 用户打开向量检索评估页面
- **THEN** 页面 SHALL 展示低分截断阈值输入框和 step delta 阈值输入框
- **AND** 用户 SHALL 可以留空任一阈值以使用后端默认配置
- **AND** 用户填写阈值时前端 SHALL 将其作为数字提交给后端
- **AND** 阈值输入非法时前端 SHALL 阻止提交并展示错误提示

#### Scenario: 用户发起检索
- **WHEN** 用户完成 Collection、Index、query、`top_k`、截断阈值和过滤标签配置后点击按钮
- **THEN** 按钮文案 SHALL 显示为“检索”
- **AND** 前端 SHALL 调用后端检索接口
- **AND** “检索”按钮 SHALL 位于“标量过滤标签”输入区域下方
- **AND** 请求 SHALL 包含 Collection 名称、Index 名称、文字 query、`top_k`、低分截断阈值、step delta 阈值和过滤标签列表

### Requirement: VikingDB 多模态检索
系统 SHALL 在后端支持基于文字 query 和指定 VikingDB Collection 发起检索，并继续在检索完成后执行 rerank 与截断链路。

#### Scenario: 后端基于文字 query 发起检索
- **WHEN** 后端收到包含 Collection 名称和文字 query 的检索请求
- **THEN** 后端 SHALL 使用请求中的 Collection 名称作为 VikingDB 检索目标
- **AND** 后端 SHALL 使用请求中的 Index 名称作为 VikingDB 检索索引
- **AND** 后端 SHALL 将文字 query 映射为 VikingDB `search_by_multi_modal` 的 text 检索输入
- **AND** 请求 SHALL 传入 `limit=top_k`
- **AND** 若用户提供过滤标签，后端 SHALL 将标签转换为 VikingDB 可接受的标量过滤参数

### Requirement: 搜索结果展示页
系统 SHALL 提供易读的向量检索搜索结果展示页，分别展示 Search 原始结果、Rerank 排序结果和截断后最终结果，并按不同阶段隐藏不相关字段。

#### Scenario: 展示 Search 原始结果
- **WHEN** 检索评估请求成功完成
- **THEN** Search 原始结果列表 SHALL 展示排序、对象、Search 分数和元数据
- **AND** Search 原始结果列表 SHALL 不展示预览列、Rerank 分数列、保留状态列和截断原因列
- **AND** 元数据 SHALL 直接展示在列表中，不再通过“查看”按钮或折叠明细入口作为唯一查看方式
- **AND** 长文本元数据 SHALL 以美观、易读方式展示，并支持展开查看完整内容
- **AND** Search 原始结果列表 SHALL 支持分页，每页最多展示 10 条

#### Scenario: 展示 Rerank 排序结果
- **WHEN** 检索评估请求成功完成并完成 rerank
- **THEN** Rerank 排序结果列表 SHALL 展示排序、对象、Search 分数、Rerank 分数和元数据
- **AND** Rerank 排序结果列表 SHALL 不展示预览列、保留状态列和截断原因列
- **AND** 元数据 SHALL 直接展示在列表中，不再通过“查看”按钮或折叠明细入口作为唯一查看方式
- **AND** 长文本元数据 SHALL 以美观、易读方式展示，并支持展开查看完整内容
- **AND** Rerank 排序结果列表 SHALL 支持分页，每页最多展示 10 条

#### Scenario: 展示截断后最终结果
- **WHEN** 检索评估请求成功完成并完成截断
- **THEN** 截断后最终结果列表 SHALL 展示排序、对象、Search 分数、Rerank 分数和元数据
- **AND** 截断后最终结果列表 SHALL 不展示预览列
- **AND** 元数据 SHALL 直接展示在列表中，不再通过“查看”按钮或折叠明细入口作为唯一查看方式
- **AND** 长文本元数据 SHALL 以美观、易读方式展示，并支持展开查看完整内容
- **AND** 截断后最终结果列表 SHALL 支持分页，每页最多展示 10 条

#### Scenario: 列表分页状态
- **WHEN** 任一结果列表超过 10 条
- **THEN** 前端 SHALL 只展示当前页最多 10 条结果
- **AND** 前端 SHALL 展示分页控制，允许用户切换上一页和下一页
- **AND** 三个结果列表 SHALL 维护相互独立的分页状态
- **AND** 用户发起新的检索并获得新结果后，各列表分页 SHALL 重置到第一页

#### Scenario: 双击标记结果条目
- **WHEN** 用户在 Search 原始结果、Rerank 排序结果或截断后最终结果任一列表中，使用鼠标左键双击某个数据条目所在行的任意位置
- **THEN** 前端 SHALL 以该条目的唯一标识在三个结果列表中同步查找同一条数据
- **AND** 如果 Search 原始结果、Rerank 排序结果和截断后最终结果三个列表都包含该条数据，三个列表中该条数据的行底色 SHALL 同步变为绿色
- **AND** 如果截断后最终结果不包含该条数据，Search 原始结果和 Rerank 排序结果中该条数据的行底色 SHALL 同步变为红色
- **AND** 已经存在绿色或红色底色的同一条数据再次被鼠标左键双击时，三个列表中该条数据的标记状态 SHALL 同步清除并恢复为白色
- **AND** 该交互 SHALL 只响应鼠标左键双击，不应由单击或其他鼠标按键触发

## REMOVED Requirements
无。
