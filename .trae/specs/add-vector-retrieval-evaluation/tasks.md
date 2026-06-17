# Tasks
- [x] Task 1: 增加后端配置与依赖说明
  - [x] SubTask 1.1: 在后端依赖中加入 `vikingdb-python-sdk`
  - [x] SubTask 1.2: 增加 VikingDB 与 Rerank 所需环境配置读取，包括 host、region、collection、index、AK/SK、Rerank endpoint 和鉴权信息
  - [x] SubTask 1.3: 缺少必要配置时返回明确错误

- [x] Task 2: 实现后端向量检索服务
  - [x] SubTask 2.1: 新增 VikingDB 检索服务，封装 `search_by_multi_modal`
  - [x] SubTask 2.2: 将数据集样本的 TOS 对象转换为 VikingDB 支持的检索输入
  - [x] SubTask 2.3: 支持 `top_k` 和 JSON 标量过滤条件传入

- [x] Task 3: 实现后端 rerank 与截断链路
  - [x] SubTask 3.1: 新增 Rerank 客户端封装，按接口要求提交候选结果
  - [x] SubTask 3.2: 按 rerank 分数倒序重排检索候选
  - [x] SubTask 3.3: 实现低分截断策略
  - [x] SubTask 3.4: 实现 step delta 截断策略
  - [x] SubTask 3.5: 在响应中返回每条结果的阶段分数、保留状态和截断原因

- [x] Task 4: 新增后端 API
  - [x] SubTask 4.1: 新增向量检索评估请求与响应 schema
  - [x] SubTask 4.2: 新增检索评估接口，串联 `search -> rerank -> 截断`
  - [x] SubTask 4.3: 对数据集不存在、参数非法、外部服务失败提供明确错误响应

- [x] Task 5: 新增前端配置与结果页面
  - [x] SubTask 5.1: 增加向量检索评估页面入口
  - [x] SubTask 5.2: 实现数据集选择、`top_k` 输入、标量过滤 JSON 输入
  - [x] SubTask 5.3: 实现提交加载态、错误提示和重试入口
  - [x] SubTask 5.4: 实现搜索结果展示，区分 search 原始结果、rerank 排序结果和截断后最终结果

- [x] Task 6: 验证
  - [x] SubTask 6.1: 增加或更新后端单元测试，覆盖过滤条件解析、rerank 排序、低分截断和 step delta 截断
  - [x] SubTask 6.2: 增加或更新前端类型检查和构建验证
  - [x] SubTask 6.3: 使用模拟外部响应验证完整 `search -> rerank -> 截断` 链路

- [x] Task 7: 接入 VikingDB Collection 列表
  - [x] SubTask 7.1: 新增后端接口，调用 BytePlus VikingDB `listVikingdbCollection` 获取 Collection 列表
  - [x] SubTask 7.2: 支持按名称关键词搜索 Collection，并返回前端下拉所需字段
  - [x] SubTask 7.3: 前端数据集下拉框改为使用 VikingDB Collection 列表，不再使用业务评测集列表

- [x] Task 8: 支持文字 query 检索
  - [x] SubTask 8.1: 后端检索请求 schema 增加 Collection 名称和文字 query
  - [x] SubTask 8.2: 后端将文字 query 映射为 VikingDB `search_by_multi_modal` 的 text 输入
  - [x] SubTask 8.3: 前端新增搜索框，并在 query 为空时阻止提交

- [x] Task 9: 调整标量过滤交互
  - [x] SubTask 9.1: 前端将标量过滤 JSON 文本框替换为标签输入控件
  - [x] SubTask 9.2: 用户输入文字并按回车后生成不可编辑、仅可删除的标签
  - [x] SubTask 9.3: 支持多个过滤标签，并提交标签列表给后端
  - [x] SubTask 9.4: 后端将过滤标签列表转换为 VikingDB 可接受的标量过滤参数

- [x] Task 10: 调整页面文案与验证
  - [x] SubTask 10.1: 将“提交评估”按钮文案改为“检索”
  - [x] SubTask 10.2: 更新后端单元测试，覆盖 Collection 列表、文字 query 和过滤标签转换
  - [x] SubTask 10.3: 更新前端构建/类型检查，验证新交互可用

- [x] Task 11: 支持按 Collection 查询并选择 VikingDB Index
  - [x] SubTask 11.1: 新增后端 Index 列表接口，调用 BytePlus VikingDB `ListVikingdbIndex` 查询指定 Collection 的 Index 列表
  - [x] SubTask 11.2: 前端在用户选择 Collection 后调用 Index 列表接口，并展示 Index 筛选框
  - [x] SubTask 11.3: 前端在检索请求中提交用户选择的 Index 名称，并在无可用 Index 时阻止检索

- [x] Task 12: 调整向量检索配置区布局
  - [x] SubTask 12.1: 将“检索”按钮移动到“标量过滤标签”输入区域下方
  - [x] SubTask 12.2: 保持 Collection、Index、query、`top_k` 和 Rerank 模型配置项可正常输入和切换

- [x] Task 13: 优化搜索结果列表展示
  - [x] SubTask 13.1: Search 原始结果列表移除预览列、Rerank 分数列、保留状态列和截断原因列
  - [x] SubTask 13.2: Rerank 排序结果列表移除预览列、保留状态列和截断原因列
  - [x] SubTask 13.3: 截断后最终结果列表移除预览列
  - [x] SubTask 13.4: 三个结果列表的元数据直接展示在列表内，移除“查看”元数据按钮
  - [x] SubTask 13.5: 长文本元数据以易读样式展示，并支持展开查看完整内容

- [x] Task 14: 验证 Index 选择与结果列表调整
  - [x] SubTask 14.1: 更新后端单元测试，覆盖 Index 列表接口和检索请求中的 Index 透传
  - [x] SubTask 14.2: 更新前端类型检查和构建验证
  - [x] SubTask 14.3: 联调验证 Collection 切换后 Index 列表刷新、检索按钮位置和结果列表列展示符合规格

- [x] Task 15: 增加截断阈值输入
  - [x] SubTask 15.1: 前端配置区增加低分截断阈值输入框和 step delta 阈值输入框
  - [x] SubTask 15.2: 前端校验阈值输入，留空时不提交该字段，填写时以数字提交给后端
  - [x] SubTask 15.3: 检索请求透传 `min_score` 和 `step_delta_threshold`，并在结果摘要中展示实际使用的阈值

- [x] Task 16: 增加三个结果列表分页
  - [x] SubTask 16.1: Search 原始结果列表支持分页，每页最多展示 10 条
  - [x] SubTask 16.2: Rerank 排序结果列表支持分页，每页最多展示 10 条
  - [x] SubTask 16.3: 截断后最终结果列表支持分页，每页最多展示 10 条
  - [x] SubTask 16.4: 三个列表维护独立分页状态，并在新检索结果返回后重置到第一页

- [x] Task 17: 验证截断阈值输入和结果分页
  - [x] SubTask 17.1: 更新前端类型检查和构建验证
  - [x] SubTask 17.2: 验证阈值输入合法/非法/留空三种场景
  - [x] SubTask 17.3: 验证三个结果列表每页最多展示 10 条，且分页状态相互独立

- [x] Task 18: 增加结果条目双击标记交互
  - [x] SubTask 18.1: 在向量检索结果页维护按数据条目唯一标识记录的标记状态
  - [x] SubTask 18.2: 为 Search 原始结果、Rerank 排序结果和截断后最终结果列表行绑定鼠标左键双击事件
  - [x] SubTask 18.3: 双击条目时判断该条数据是否同时存在于三个列表，并将三个列表中的同一条数据同步标记为绿色
  - [x] SubTask 18.4: 当截断后最终结果不包含该条数据时，将 Search 原始结果和 Rerank 排序结果中的同一条数据同步标记为红色
  - [x] SubTask 18.5: 已标记条目再次被鼠标左键双击时，清除三个列表中的同步标记并恢复白色底色

- [x] Task 19: 验证结果条目标记交互
  - [x] SubTask 19.1: 验证点击行内任意位置的鼠标左键双击均可触发标记
  - [x] SubTask 19.2: 验证绿色、红色和再次双击恢复白色三种状态符合规格
  - [x] SubTask 19.3: 验证三个结果列表对同一条数据的标记状态保持同步
  - [x] SubTask 19.4: 运行前端类型检查、构建和目标页面 lint

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 1, Task 2, Task 3, Task 4 and Task 5
- Task 8 depends on Task 7
- Task 9 depends on Task 8
- Task 10 depends on Task 7, Task 8 and Task 9
- Task 11 depends on Task 7
- Task 12 depends on Task 11
- Task 13 depends on Task 10
- Task 14 depends on Task 11, Task 12 and Task 13
- Task 15 depends on Task 10
- Task 16 depends on Task 13
- Task 17 depends on Task 15 and Task 16
- Task 18 depends on Task 13 and Task 16
- Task 19 depends on Task 18
