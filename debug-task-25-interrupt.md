# Debug Session: task-25-interrupt
- **Status**: [OPEN]
- **Issue**: `task 25` 运行到 97 条 `completed` 后中断，55 条结果未开始执行并被收尾标记为 `failed`
- **Debug Server**: http://127.0.0.1:7777/event
- **Log File**: `.dbg/trae-debug-log-task-25-interrupt.ndjson`

## Reproduction Steps
1. 打开 `tasks/25` 详情页并运行任务。
2. 观察任务顶层状态最终变为 `failed`。
3. 查看结果详情，可见 `97` 条 `completed`、`55` 条失败，失败原因为“任务执行中断，结果未开始执行”。

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | 线程池批次循环在某一批之前被任务级异常中断，后续 55 条未提交给 worker | High | Med | Pending |
| B | worker 最前置查询 `TaskResult / EvaluationData` 时异常返回，导致结果看似未开始执行 | Med | Low | Pending |
| C | 模型调用线程存在未被当前日志覆盖的阻塞/异常，触发主循环提前收尾 | Med | Med | Pending |
| D | 数据库连接/会话在长批处理中异常，导致后续批次推进失败 | Med | Med | Pending |

## Log Evidence
- 已启动 Debug Server：`http://127.0.0.1:7777/event`
- 已在 `backend/app/api/tasks.py` 增加运行时埋点：
  - 任务总批次开始
  - 每批开始/结束
  - worker 前置查询
  - worker 进入 running
  - worker 完成 / 失败
  - 任务收尾时的残留 `pending` 计数
- 复现 `task 25` 结果：
  - 第 1 批完成时 `has_failure_so_far=false`
  - 第 2 批开始出现失败迹象，但任务继续推进到后续批次
  - 任务收尾日志显示：`has_failure=true`、`pending_count=26`
- 对可疑长尾样本的证据：
  - 预检查日志显示 `data_id=458/460/476/483` 均能查到 `TaskResult` 和 `EvaluationData`
  - 这些样本在数据库中长时间停留为 `running`
  - 当前代码中火山请求 `annotate_with_usage()` 未设置显式超时
- 已排除的假设：
  - `B`：前置查询缺记录不是主因
  - “所有视频抽帧都卡住”不是主因，大量视频可正常完成抽帧并完成火山请求
- 尚未完全区分：
  - 4 条长尾 `mp4` 是卡在视频抽帧，还是卡在火山请求；现有二层埋点未附带 `data_id` 到阶段日志

## Verification Conclusion
- 当前最强结论：`task 25` 中断的直接原因是少量长尾 `mp4` worker 长时间未结束，导致任务收尾时仍有 26 条未启动结果，被统一标记为 `failed`。
- 当前最强怀疑：长尾发生在视频推理链路内部，且火山请求没有显式超时保护，存在单请求长时间不返回的风险。
