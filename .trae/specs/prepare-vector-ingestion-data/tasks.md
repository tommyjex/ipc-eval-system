# Tasks
- [x] Task 1: 梳理数据源与输出结构
  - [x] SubTask 1.1: 确认 `/datasets/7` 对应数据库中的 `dataset_id=7`
  - [x] SubTask 1.2: 确认评测数据、标注结果、文件名和 TOS 信息的模型字段
  - [x] SubTask 1.3: 定义输出 JSON 每条记录结构，包含数据 ID、文件名、TOS 信息、原始标注 JSON 和英文标注 JSON

- [x] Task 2: 实现标注数据抽取脚本
  - [x] SubTask 2.1: 在 `backend/scripts` 新增脚本，支持从后端数据库连接读取 `dataset_id=7` 数据
  - [x] SubTask 2.2: 仅处理存在有效标注结果的数据
  - [x] SubTask 2.3: 校验可处理记录数量必须为 `215`
  - [x] SubTask 2.4: 支持命令行参数指定输出文件路径

- [x] Task 3: 实现 JSON 解析与结构保持
  - [x] SubTask 3.1: 将每条标注结果解析为 JSON
  - [x] SubTask 3.2: 对对象、数组、字符串进行递归遍历
  - [x] SubTask 3.3: 保持字段名、字段顺序、数组顺序、数字、布尔值和空值不变
  - [x] SubTask 3.4: 对非法 JSON 输出数据 ID 和失败原因，并失败退出

- [x] Task 4: 实现中文到英文翻译
  - [x] SubTask 4.1: 识别 JSON 字符串值中包含中文的内容
  - [x] SubTask 4.2: 调用项目可用的大模型或翻译能力，将中文字符串翻译为英文
  - [x] SubTask 4.3: 翻译失败时记录数据 ID、字段路径和错误原因
  - [x] SubTask 4.4: 避免翻译 JSON 字段名，确保只翻译字符串值中的中文内容

- [x] Task 5: 输出并校验 JSON 文件
  - [x] SubTask 5.1: 生成包含 `215` 条记录的 JSON 文件
  - [x] SubTask 5.2: 输出前使用临时文件，全部成功后再写入正式文件
  - [x] SubTask 5.3: 输出后重新读取文件，校验合法 JSON 和记录数量
  - [x] SubTask 5.4: 打印输出路径、记录数量和翻译统计信息

- [x] Task 6: 验证
  - [x] SubTask 6.1: 增加或更新单元测试，覆盖中文检测、递归翻译、结构保持和非法 JSON 失败
  - [x] SubTask 6.2: 使用模拟翻译器验证脚本可生成 `215` 条结构正确的输出
  - [x] SubTask 6.3: 在本地运行脚本的 dry-run 或模拟模式，确认不会生成不完整正式文件

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 2, Task 3, Task 4 and Task 5
