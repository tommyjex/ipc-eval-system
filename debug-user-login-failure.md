# [OPEN] debug-user-login-failure

## 问题
- 现象：新创建用户 `xujianhua` 登录失败，提示“用户名密码错误”。
- 目标：确认登录失败发生在哪个环节，并修复为“管理员创建的普通用户可正常登录”。

## 初始假设
1. 登录接口仍只校验 `.env` 管理员账号，没有查询 `users` 表。
2. 创建用户写入了哈希密码，但登录校验仍按明文或另一种算法校验，导致恒失败。
3. 新用户已被写入 `users` 表，但状态不是 `active` 或命中逻辑删除条件。
4. 创建用户落库成功，但登录接口读取的数据库连接/会话与写入不一致。
5. 前端登录请求参数没问题，但错误信息被统一为“用户名密码错误”，掩盖了真实后端异常。

## 当前计划
1. 调用登录接口复现并查看返回。
2. 查询数据库中 `xujianhua` 用户记录与 `password_hash/status/deleted_at`。
3. 对照 `auth` 登录逻辑判断根因，再做最小修复。

## 当前证据
- `POST /api/auth/login` 对 `xujianhua` 返回 `401`，错误为“用户名或密码错误”。
- 数据库中 `users.username = 'xujianhua'` 记录存在，且：
  - `status = active`
  - `deleted_at = None`
  - `password_hash` 已有值
- 运行时插桩日志显示：
  - `input_username = xujianhua`
  - `admin_username = admin`
  - `username_match = false`
  - `password_match = true`

## 假设结论
1. 登录接口仍只校验 `.env` 管理员账号，没有查询 `users` 表：`成立`
2. 创建用户写入了哈希密码，但登录校验算法不一致：`当前证据不支持`
3. 新用户状态异常或被逻辑删除：`已排除`
4. 数据库写入与读取不一致：`已排除`
5. 后端抛了其他异常但被统一文案掩盖：`已排除`

## 当前判断
- 根因是登录链路尚未接入 `users` 表。
- 当前系统处于“管理员后台已做，但认证仍是固定管理员模式”的中间态。

## 修复结果
- 已在 `auth.py` 中保留管理员固定账号登录能力，同时新增：
  - 查询 `users` 表
  - 校验 `deleted_at is null`
  - 校验 `status = active`
  - 校验 `sha256(password)` 与 `password_hash` 一致
- 认证测试已通过：`3 passed`
- 本地重启后复验：
  - `POST /api/auth/login` with `xujianhua` => `200 OK`
  - 返回 `{"username":"xujianhua"}`
  - 成功下发 `ipc_eval_session` cookie
