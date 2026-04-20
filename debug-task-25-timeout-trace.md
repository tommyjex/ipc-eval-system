# Debug Session: task-25-timeout-trace
- **Status**: [OPEN]
- **Issue**: `task 25` 中 3 条 `mp4` 超时失败，需要定位具体卡在哪一步
- **Debug Server**: http://127.0.0.1:7777/event
- **Target Samples**:
  - `data_id=393` `08-2025-03-20-08-01-35-小孩看成了快递员.mp4`
  - `data_id=422` `27-20250312上学2.mp4`
  - `data_id=436` `46-20250317-1817-送快递的人遇到宝宝出门.mp4`

## Reproduction Steps
1. 重置并重跑 `task 25`，或仅重跑超时的 3 条视频。
2. 观察单条结果被标记为 `单条任务执行超时（执行时间 >120s）`。
3. 收集运行时日志，定位卡点发生在下载、抽帧、上传、还是模型请求。

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | 卡在 `extract_video_frames()` 的视频下载阶段 | Medium | Low | Pending |
| B | 卡在抽帧或帧上传 TOS 阶段 | Medium | Medium | Pending |
| C | 卡在 `annotate_with_usage()` 的火山请求阶段 | High | Medium | Pending |
| D | 子进程通信/收尾异常导致被误判为超时 | Medium | Medium | Pending |

## Log Evidence
- 已启动 Debug Server：`http://127.0.0.1:7777/event`
- 已在以下阶段加入埋点：
  - `_run_single_task_result`：视频内容构建开始/结束、火山请求开始/结束
  - `extract_video_frames()`：下载开始/完成、抽帧完成
  - `annotate_with_usage()`：火山请求开始/返回
- 只重跑 `data_id=393/422/436` 后，3 条均完成，且日志完整：
  - `393`：下载完成、抽帧完成、火山请求返回、最终 `completed`
  - `422`：下载完成、抽帧完成、火山请求返回、最终 `completed`
  - `436`：下载完成、抽帧完成、火山请求返回、最终 `completed`
- 分阶段观察：
  - 下载阶段约 `3s - 9s`
  - 抽帧+上传阶段约 `24s - 29s`
  - 火山请求阶段约 `5s - 8s`
- 当前最重的阶段不是火山请求，而是视频抽帧/上传阶段

## Verification Conclusion
- `A` 部分否定：下载不是主瓶颈，虽然存在秒级差异，但都能顺利完成。
- `B` 当前最强：抽帧/上传是最重阶段，单条视频约消耗 `24s - 29s`。
- `C` 否定为主要瓶颈：火山请求均有返回，耗时约 `5s - 8s`。
- `D` 暂无证据支持：本次 3 条子进程执行与收尾均正常。
- 当前结论：整任务场景下的超时更像是高并发资源竞争导致单条总耗时被放大，而不是这 3 条在某一步固定卡死。
