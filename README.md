# 摄像头场景大模型评测平台

摄像头场景的大模型应用效果评测平台，提供数据集管理、标注、模型选择、评测、打分、报告生成等核心功能。

## 技术栈

- **前端**: TypeScript + React + Vite
- **后端**: Python + FastAPI
- **数据库**: MySQL
- **存储**: 对象存储（用于图片/视频数据）

## 项目结构

```
.
├── frontend/                # 前端项目
│   ├── src/
│   │   ├── api/            # API 请求
│   │   ├── components/     # 组件
│   │   ├── hooks/          # 自定义 Hooks
│   │   ├── pages/          # 页面
│   │   └── utils/          # 工具函数
│   └── package.json
├── backend/                 # 后端项目
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   ├── tests/              # 测试
│   └── requirements.txt
└── openspec/               # 规范文档
```

## 快速开始

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 后端

```bash
cd backend
pip install -r requirements.txt
python run.py
```

## 功能模块

- 数据集管理
- 数据标注
- 模型选择
- 评测配置
- 自动打分
- 报告生成

## 开发规范

- 使用中文编写文档、注释和提交信息
- 遵循 ESLint / Prettier 代码格式化规范
- 组件命名采用 PascalCase，函数/变量采用 camelCase
- 文件命名采用 kebab-case
