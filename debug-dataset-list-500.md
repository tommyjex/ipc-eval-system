# [OPEN] dataset-list-500

## 症状
- 前端请求 `/api/datasets?page=1&page_size=50` 返回 500
- 页面提示“获取评测集列表失败”

## 预期
- 后端返回 200
- 前端正常展示评测集列表

## 可证伪假设
- 假设 1：后端查询数据库时报错，导致列表接口直接 500
- 假设 2：数据库连接已建立，但返回字段与当前 ORM / schema 不一致
- 假设 3：评测集列表序列化阶段访问关联字段时报错
- 假设 4：前端代理正常，500 来自后端真实异常而非前端拼接 URL 错误

## 当前状态
- 已创建调试会话，准备复现并收集运行时证据

## 运行时证据
- 直接请求 `GET /api/datasets?page=1&page_size=50` 复现 500
- 后端堆栈显示 `sqlalchemy.exc.OperationalError`
- 具体错误为 `Can't connect to MySQL server on 'mysqlf4d4d1585fb1.rds.ivolces.com'`
- 本地 DNS 解析该域名返回 `NXDOMAIN`

## 假设结论
- 假设 1：成立，数据库连接阶段失败
- 假设 2：不成立，尚未进入字段映射或 ORM 结果处理阶段
- 假设 3：不成立，尚未进入序列化阶段
- 假设 4：成立，500 来自后端真实异常

## 修复动作
- 将本地后端环境变量中的 `DB_HOST` 改为可解析的公网地址
- 重启后端服务，使新的环境变量生效

## 修复后证据
- 直接请求 `GET /api/datasets?page=1&page_size=50` 返回 `200 OK`
- 通过前端代理请求 `GET http://127.0.0.1:5175/api/datasets?page=1&page_size=50` 也返回 `200 OK`

## 当前结论
- 根因是数据库地址不可解析，不是前端代码问题
- 当前修复已生效，等待页面侧人工确认
