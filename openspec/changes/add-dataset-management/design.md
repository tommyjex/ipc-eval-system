## 上下文
评测集管理是评测平台的核心模块，需要处理大量视频/图片数据的上传、存储和标注。系统需要集成TOS对象存储、火山方舟大模型API，并提供友好的用户界面。

### 利益相关者
- 评测人员：创建评测集、上传数据、进行标注
- 系统管理员：管理评测数据、监控系统状态

### 约束
- 单个视频文件最大支持500MB
- 单个图片文件最大支持20MB
- GIF图片需要支持多帧解析
- 大模型标注需要支持异步处理

## 目标 / 非目标

### 目标
- 提供简洁的评测集创建流程
- 支持灵活的数据导入方式
- 提供高效的标注工具
- 确保数据存储的可靠性

### 非目标
- 视频编辑功能
- 图片编辑功能
- 实时协作标注

## 决策

### 技术选型

| 组件 | 技术方案 | 安装命令 |
|------|----------|----------|
| TOS Python SDK | 火山引擎 TOS SDK | `pip install tos` |
| TOS Node.js SDK | 火山引擎 TOS SDK | `npm i @volcengine/tos-sdk` |
| 大模型 SDK | 火山方舟 SDK | `pip install 'volcengine-python-sdk[ark]'` |
| 大模型 API | Responses API | 端点: `https://ark.cn-beijing.volces.com/api/v3/responses` |

### 数据存储架构
- **决策**：使用TOS对象存储存储原始文件，MySQL存储元数据
- **原因**：
  - TOS适合存储大文件，提供高可用性和低成本
  - MySQL适合存储结构化数据，支持复杂查询
- **object key设计**：`datasets/{dataset_id}/{data_type}/{uuid}.{ext}`

### 文件上传策略
- **决策**：前端直传TOS，后端生成预签名URL
- **原因**：
  - 避免文件经过后端服务器，减少带宽压力
  - 预签名URL保证安全性
- **替代方案**：文件上传到后端，后端再上传TOS
  - 缺点：增加服务器负载，上传速度受限于服务器带宽

### 标注流程设计
- **决策**：大模型标注采用异步任务队列处理
- **原因**：
  - 大模型API调用耗时较长
  - 批量标注需要并行处理
- **技术选型**：使用Celery + Redis作为任务队列

### 大模型调用方式
- **决策**：使用火山方舟 Responses API
- **原因**：
  - 支持多模态输入（文本、图片、视频）
  - 支持上下文缓存
  - 统一的API接口
- **调用示例**：
```python
from volcengine.ark import Ark

client = Ark(api_key="your-api-key")
response = client.responses.create(
    model="doubao-seed-1.6",
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "请描述这张图片的内容"},
                {"type": "input_image", "image_url": "https://example.com/image.jpg"}
            ]
        }
    ]
)
```

### 数据库表设计
```sql
-- 评测集表
CREATE TABLE datasets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type ENUM('video', 'image') NOT NULL,
    status ENUM('draft', 'ready', 'archived') DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP
);

-- 评测数据表
CREATE TABLE evaluation_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    dataset_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    tos_key VARCHAR(500) NOT NULL,
    tos_bucket VARCHAR(100) NOT NULL,
    status ENUM('pending', 'annotated', 'failed') DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

-- 标注记录表
CREATE TABLE annotations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    data_id BIGINT NOT NULL,
    ground_truth TEXT NOT NULL,
    annotation_type ENUM('manual', 'ai') NOT NULL,
    model_name VARCHAR(100),
    annotator_id BIGINT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (data_id) REFERENCES evaluation_data(id)
);
```

## 风险 / 权衡

### 风险1：大文件上传超时
- **缓解措施**：使用分片上传，支持断点续传

### 风险2：大模型标注成本
- **缓解措施**：提供批量标注预览，用户确认后再调用API

### 风险3：TOS服务不可用
- **缓解措施**：实现降级策略，临时存储到本地，待TOS恢复后同步

## 迁移计划
1. 创建数据库表结构
2. 配置TOS SDK（后端 + 前端）
3. 配置火山方舟 SDK
4. 实现后端API
5. 开发前端界面
6. 集成测试

## 待决问题
- [x] TOS SDK选型：火山引擎官方SDK
- [x] 大模型SDK选型：火山方舟 Python SDK
- [x] 大模型API：Responses API
- [ ] TOS bucket命名规范
- [ ] 大模型标注的具体提示词模板
- [ ] 标注结果的格式定义（JSON Schema）
