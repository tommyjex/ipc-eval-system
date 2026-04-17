import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { taskApi, datasetApi, scoringTemplateApi, promptTemplateApi } from '../../api';
import type { EvaluationTask, TaskResultDetail, TaskStatus, TaskScoringStatus, TaskResultStatus, DatasetScene, ScoringTemplate, PromptTemplate } from '../../api';

const getRecentTemplateStorageKey = (scene: DatasetScene) => `recent-scoring-template:${scene}`;
const getRecentPromptTemplateStorageKey = (scene: DatasetScene) => `recent-prompt-template:${scene}`;
const normalizeFps = (value: number) => Math.max(0.01, Math.min(30, Number(value.toFixed(2))));
const formatNullableNumber = (value: number | null | undefined, digits = 1, suffix = '') =>
  (typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(digits)}${suffix}` : '-');
const normalizeResultDetail = (result: Partial<TaskResultDetail>): TaskResultDetail => ({
  id: result.id ?? 0,
  task_id: result.task_id ?? 0,
  data_id: result.data_id ?? 0,
  status: (result.status ?? 'pending') as TaskResultStatus,
  model_output: result.model_output ?? null,
  input_tokens: result.input_tokens ?? null,
  output_tokens: result.output_tokens ?? null,
  score: result.score ?? null,
  recall: result.recall ?? null,
  accuracy: result.accuracy ?? null,
  score_reason: result.score_reason ?? null,
  scoring_status: (result.scoring_status ?? 'not_scored') as TaskScoringStatus,
  scoring_error_message: result.scoring_error_message ?? null,
  scoring_model: result.scoring_model ?? null,
  scoring_started_at: result.scoring_started_at ?? null,
  scoring_completed_at: result.scoring_completed_at ?? null,
  error_message: result.error_message ?? null,
  created_at: result.created_at ?? '',
  updated_at: result.updated_at ?? null,
  completed_at: result.completed_at ?? null,
  file_name: result.file_name ?? '',
  file_type: result.file_type ?? '',
  download_url: result.download_url ?? null,
  ground_truth: result.ground_truth ?? null,
});

export const TaskDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<EvaluationTask | null>(null);
  const [datasetName, setDatasetName] = useState('');
  const [datasetScene, setDatasetScene] = useState<DatasetScene | null>(null);
  const [datasetCustomTags, setDatasetCustomTags] = useState<string[]>([]);
  const [templates, setTemplates] = useState<ScoringTemplate[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [results, setResults] = useState<TaskResultDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    scoring_criteria: '',
    prompt: '',
    fps: 0.3,
  });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState<50 | 100>(50);
  const [resultStatusFilter, setResultStatusFilter] = useState<'all' | TaskResultStatus>('all');
  const [scoringStatusFilter, setScoringStatusFilter] = useState<'all' | TaskScoringStatus>('all');
  const [avgRecall, setAvgRecall] = useState<number | null>(null);
  const [avgAccuracy, setAvgAccuracy] = useState<number | null>(null);
  const [avgInputTokens, setAvgInputTokens] = useState<number | null>(null);
  const [avgOutputTokens, setAvgOutputTokens] = useState<number | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<TaskResultDetail | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [selectedPromptTemplateId, setSelectedPromptTemplateId] = useState('');
  const pollingRef = useRef(false);

  const fetchTaskInfo = async (options?: { silent?: boolean }) => {
    if (!id) return;
    const silent = options?.silent ?? false;
    if (silent && pollingRef.current) return;
    if (silent) {
      pollingRef.current = true;
    }

    try {
      const taskRes = await taskApi.get(parseInt(id));
      setTask(taskRes);

      // 静默轮询时不要重置编辑态、展开态和评测集展示，避免整页闪动。
      if (!silent) {
        setPromptExpanded(false);
        setDatasetName('');
        setDatasetScene(null);
        setDatasetCustomTags([]);
        setEditForm({
          name: taskRes.name,
          scoring_criteria: taskRes.scoring_criteria || '',
          prompt: taskRes.prompt || '',
          fps: taskRes.fps || 0.3,
        });
      }

      try {
        if (!silent) {
          const datasetRes = await datasetApi.get(taskRes.dataset_id);
          setDatasetName(datasetRes.name);
          setDatasetScene(datasetRes.scene);
          setDatasetCustomTags(datasetRes.custom_tags || []);
          if (datasetRes.scene) {
            const templateRes = await scoringTemplateApi.list({ scene: datasetRes.scene });
            setTemplates(templateRes.items);
            const promptTemplateRes = await promptTemplateApi.list({ scene: datasetRes.scene });
            setPromptTemplates(promptTemplateRes.items);
          } else {
            setTemplates([]);
            setPromptTemplates([]);
          }
        }
      } catch (err) {
        console.error('获取评测集信息失败:', err);
      }
    } catch (err) {
      console.error('获取任务详情失败:', err);
    } finally {
      if (silent) {
        pollingRef.current = false;
      }
    }
  };

  const fetchResults = async (options?: { silent?: boolean }) => {
    if (!id) return;
    const silent = options?.silent ?? false;
    if (!silent) {
      setResultsLoading(true);
    }

    try {
      const resultsRes = await taskApi.getResultsDetail(parseInt(id), {
        page,
        page_size: pageSize,
        status: resultStatusFilter === 'all' ? undefined : resultStatusFilter,
        scoring_status: scoringStatusFilter === 'all' ? undefined : scoringStatusFilter,
      });
      const detailItems = Array.isArray(resultsRes)
        ? resultsRes
        : Array.isArray(resultsRes.items)
          ? resultsRes.items
          : [];
      setResults(detailItems.map((item) => normalizeResultDetail(item as Partial<TaskResultDetail>)));
      setTotal(typeof resultsRes === 'object' && resultsRes !== null && 'total' in resultsRes && typeof resultsRes.total === 'number'
        ? resultsRes.total
        : detailItems.length);
      setAvgRecall(typeof resultsRes === 'object' && resultsRes !== null && 'avg_recall' in resultsRes && typeof resultsRes.avg_recall === 'number' ? resultsRes.avg_recall : null);
      setAvgAccuracy(typeof resultsRes === 'object' && resultsRes !== null && 'avg_accuracy' in resultsRes && typeof resultsRes.avg_accuracy === 'number' ? resultsRes.avg_accuracy : null);
      setAvgInputTokens(typeof resultsRes === 'object' && resultsRes !== null && 'avg_input_tokens' in resultsRes && typeof resultsRes.avg_input_tokens === 'number' ? resultsRes.avg_input_tokens : null);
      setAvgOutputTokens(typeof resultsRes === 'object' && resultsRes !== null && 'avg_output_tokens' in resultsRes && typeof resultsRes.avg_output_tokens === 'number' ? resultsRes.avg_output_tokens : null);
    } catch (err) {
      console.error('获取评测结果失败:', err);
    } finally {
      if (!silent) {
        setResultsLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const initialize = async () => {
      setLoading(true);
      try {
        await fetchTaskInfo();
        await fetchResults({ silent: true });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    initialize();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!id || loading) return;
    fetchResults();
  }, [id, page, pageSize, resultStatusFilter, scoringStatusFilter, loading]);

  useEffect(() => {
    if (!saveSuccess) return;
    const timer = window.setTimeout(() => setSaveSuccess(''), 3000);
    return () => window.clearTimeout(timer);
  }, [saveSuccess]);

  useEffect(() => {
    if (task?.status !== 'running') return;
    const timer = window.setInterval(() => {
      fetchTaskInfo({ silent: true });
      fetchResults({ silent: true });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [task?.status, id, page, pageSize, resultStatusFilter, scoringStatusFilter]);

  useEffect(() => {
    if (!editing || !datasetScene) {
      if (!editing) {
        setSelectedTemplateId('');
        setSelectedPromptTemplateId('');
      }
      return;
    }

    const recentTemplateId = window.localStorage.getItem(getRecentTemplateStorageKey(datasetScene));
    const recentTemplate = templates.find((template) => String(template.id) === recentTemplateId);
    if (!recentTemplate) {
      setSelectedTemplateId('');
      return;
    }

    setSelectedTemplateId(String(recentTemplate.id));
    setEditForm((prev) => (
      prev.scoring_criteria.trim()
        ? prev
        : { ...prev, scoring_criteria: recentTemplate.content }
    ));

    const recentPromptTemplateId = window.localStorage.getItem(getRecentPromptTemplateStorageKey(datasetScene));
    const recentPromptTemplate = promptTemplates.find((template) => String(template.id) === recentPromptTemplateId);
    if (!recentPromptTemplate) {
      setSelectedPromptTemplateId('');
      return;
    }

    setSelectedPromptTemplateId(String(recentPromptTemplate.id));
    setEditForm((prev) => (
      prev.prompt.trim()
        ? prev
        : { ...prev, prompt: recentPromptTemplate.content }
    ));
  }, [editing, datasetScene, templates, promptTemplates]);

  const handleRun = async (dataIds?: number[]) => {
    if (!id) return;
    try {
      await taskApi.run(parseInt(id), dataIds && dataIds.length > 0 ? { data_ids: dataIds } : undefined);
      await fetchTaskInfo({ silent: true });
      await fetchResults({ silent: true });
    } catch (err) {
      alert('启动失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleRunFiltered = async () => {
    if (!id || resultStatusFilter === 'all') return;
    try {
      const selection = await taskApi.getResultSelection(parseInt(id), { status: resultStatusFilter });
      if (selection.data_ids.length === 0) {
        alert('当前筛选条件下没有可运行结果');
        return;
      }
      await handleRun(selection.data_ids);
    } catch (err) {
      alert('获取筛选结果失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm('确定要删除这个任务吗？')) return;
    try {
      await taskApi.delete(parseInt(id));
      navigate('/tasks');
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleEditCancel = () => {
    if (!task) return;
    setEditForm({
      name: task.name,
      scoring_criteria: task.scoring_criteria || '',
      prompt: task.prompt || '',
      fps: task.fps || 0.3,
    });
    setSaveSuccess('');
    setPromptExpanded(false);
    setEditing(false);
  };

  const handleSave = async () => {
    if (!id || !task || !editForm.name.trim()) return;
    setSaving(true);
    try {
      await taskApi.update(parseInt(id), {
        name: editForm.name.trim(),
        scoring_criteria: editForm.scoring_criteria,
        prompt: editForm.prompt,
        fps: editForm.fps,
      });
      setEditing(false);
      await fetchTaskInfo();
      setSaveSuccess('任务信息已保存');
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSaving(false);
    }
  };

  const handleSmartScore = async (resultIds?: number[]) => {
    if (!id) return;
    setScoring(true);
    try {
      const result = await taskApi.score(parseInt(id), resultIds && resultIds.length > 0 ? { result_ids: resultIds } : undefined);
      await fetchTaskInfo();
      await fetchResults({ silent: true });
      if (result.scored_count > 0) {
        setSaveSuccess(`智能评分已完成，成功评分 ${result.scored_count} 条${result.failed_count > 0 ? `，失败 ${result.failed_count} 条` : ''}`);
      } else if (result.failed_count > 0) {
        setSaveSuccess(`智能评分执行完成，但失败 ${result.failed_count} 条`);
      } else {
        setSaveSuccess(`没有可评分结果，已跳过 ${result.skipped_count} 条`);
      }
    } catch (err) {
      alert('智能评分失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setScoring(false);
    }
  };

  const handleSmartScoreFiltered = async () => {
    if (!id || scoringStatusFilter === 'all') return;
    setScoring(true);
    try {
      const selection = await taskApi.getResultSelection(parseInt(id), { scoring_status: scoringStatusFilter });
      if (selection.result_ids.length === 0) {
        setSaveSuccess('当前筛选条件下没有可评分结果');
        return;
      }
      const result = await taskApi.score(parseInt(id), { result_ids: selection.result_ids });
      await fetchTaskInfo();
      await fetchResults({ silent: true });
      if (result.scored_count > 0) {
        setSaveSuccess(`智能评分已完成，成功评分 ${result.scored_count} 条${result.failed_count > 0 ? `，失败 ${result.failed_count} 条` : ''}`);
      } else if (result.failed_count > 0) {
        setSaveSuccess(`智能评分执行完成，但失败 ${result.failed_count} 条`);
      } else {
        setSaveSuccess(`没有可评分结果，已跳过 ${result.skipped_count} 条`);
      }
    } catch (err) {
      alert('筛选评分失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setScoring(false);
    }
  };

  const closePreview = () => {
    setShowPreview(false);
    setPreviewData(null);
  };

  const openPreview = (data: TaskResultDetail) => {
    setPreviewData(data);
    setShowPreview(true);
  };

  const getStatusBadge = (status: TaskStatus) => {
    const styles: Record<TaskStatus, string> = {
      pending: 'bg-gray-100 text-gray-800',
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    const labels: Record<TaskStatus, string> = {
      pending: '待运行',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
    };
    return (
      <span className={`px-2 py-1 rounded text-xs ${styles[status]}`}>
        {labels[status]}
      </span>
    );
  };

  const getScoringStatusBadge = (status: TaskScoringStatus | undefined) => {
    const normalizedStatus = status ?? 'not_scored';
    const styles: Record<TaskScoringStatus, string> = {
      not_scored: 'bg-gray-100 text-gray-800',
      scoring: 'bg-blue-100 text-blue-800',
      scored: 'bg-green-100 text-green-800',
      score_failed: 'bg-red-100 text-red-800',
    };
    const labels: Record<TaskScoringStatus, string> = {
      not_scored: '未评分',
      scoring: '评分中',
      scored: '已评分',
      score_failed: '评分失败',
    };
    return (
      <span className={`px-2 py-1 rounded text-xs ${styles[normalizedStatus]}`} title={normalizedStatus === 'score_failed' ? '评分失败，可重试' : labels[normalizedStatus]}>
        {labels[normalizedStatus]}
      </span>
    );
  };

  const renderHoverText = (text: string | null | undefined, fallback = '-') => {
    const displayText = text?.trim() || fallback;
    return (
      <div className="group relative max-w-xs">
        <p className="cursor-default truncate text-sm text-gray-600" title={displayText}>
          {displayText}
        </p>
        {text?.trim() && (
          <div className="absolute left-0 top-full z-20 hidden pt-1 group-hover:block pointer-events-auto">
            <div className="max-w-md rounded border bg-white p-3 text-sm text-gray-700 shadow-lg">
              <div className="mb-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(text)}
                  className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                >
                  复制
                </button>
              </div>
              <div className="max-h-64 overflow-auto whitespace-pre-wrap select-text cursor-text">
                {text}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const isVideo = (fileType: string) => 
    ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'].includes(fileType.toLowerCase());
  const sceneLabelMap: Record<DatasetScene, string> = {
    video_retrieval: '视频检索',
    smart_alert: '智能告警',
  };

  const shouldCollapsePrompt =
    !!task?.prompt && (task.prompt.length > 200 || task.prompt.includes('\n'));
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (loading) {
    return <div className="p-6 text-center">加载中...</div>;
  }

  if (!task) {
    return <div className="p-6 text-center text-gray-500">任务不存在</div>;
  }

  return (
    <div className="p-6">
      <div className="sticky top-0 z-20 -mx-6 mb-6 bg-gray-50/95 px-6 pb-4 pt-6 backdrop-blur">
        <div className="mb-4">
          <button
            onClick={() => navigate('/tasks')}
            className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
          >
            返回任务列表
          </button>
        </div>
        <div className="rounded-lg bg-white p-6 shadow">
          {saveSuccess && (
            <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
              {saveSuccess}
            </div>
          )}
          <div className="flex justify-between items-start gap-6">
            <div className="flex-1 min-w-0">
              {editing ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">任务名称</label>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      className="w-full max-w-md px-3 py-2 border rounded"
                      placeholder="请输入任务名称"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">评分标准</label>
                    {datasetScene ? (
                      <select
                        value={selectedTemplateId}
                        onChange={(e) => {
                          setSelectedTemplateId(e.target.value);
                          const template = templates.find((item) => String(item.id) === e.target.value);
                          if (template) {
                            window.localStorage.setItem(getRecentTemplateStorageKey(datasetScene), String(template.id));
                            setEditForm({ ...editForm, scoring_criteria: template.content });
                          }
                        }}
                        className="mb-2 w-full max-w-md rounded border px-3 py-2"
                      >
                        <option value="">选择{sceneLabelMap[datasetScene]}模板</option>
                        {templates.map((template) => (
                          <option key={template.id} value={template.id}>
                            {template.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="mb-2 text-xs text-gray-500">当前评测集未配置业务场景，无法筛选评分模板。</p>
                    )}
                    <textarea
                      value={editForm.scoring_criteria}
                      onChange={(e) => setEditForm({ ...editForm, scoring_criteria: e.target.value })}
                      className="w-full px-3 py-2 border rounded"
                      rows={4}
                      placeholder="请输入评分标准"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频帧率 (fps)</label>
                    <input
                      type="number"
                      min={0.01}
                      max={30}
                      step={0.01}
                      value={editForm.fps}
                      onChange={(e) => setEditForm({ ...editForm, fps: normalizeFps(Number(e.target.value) || 0.3) })}
                      className="w-full max-w-md px-3 py-2 border rounded"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Prompt</label>
                    {datasetScene ? (
                      <select
                        value={selectedPromptTemplateId}
                        onChange={(e) => {
                          setSelectedPromptTemplateId(e.target.value);
                          const template = promptTemplates.find((item) => String(item.id) === e.target.value);
                          if (template) {
                            window.localStorage.setItem(getRecentPromptTemplateStorageKey(datasetScene), String(template.id));
                            setEditForm({ ...editForm, prompt: template.content });
                          }
                        }}
                        className="mb-2 w-full max-w-md rounded border px-3 py-2"
                      >
                        <option value="">选择{sceneLabelMap[datasetScene]}Prompt模板</option>
                        {promptTemplates.map((template) => (
                          <option key={template.id} value={template.id}>
                            {template.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p className="mb-2 text-xs text-gray-500">当前评测集未配置业务场景，无法筛选 Prompt 模板。</p>
                    )}
                    <textarea
                      value={editForm.prompt}
                      onChange={(e) => setEditForm({ ...editForm, prompt: e.target.value })}
                      className="w-full px-3 py-2 border rounded"
                      rows={5}
                      placeholder="请输入任务级 Prompt"
                    />
                  </div>
                </div>
              ) : (
                <h1 className="text-2xl font-bold mb-2">{task.name}</h1>
              )}
              <div className="flex items-center space-x-4 text-sm">
                <span className="text-gray-600">评测集: {datasetName || task.dataset_id}</span>
                <span className="text-gray-600">目标模型: {task.target_model}</span>
                {getStatusBadge(task.status)}
              </div>
            </div>
            <div className="flex space-x-2 shrink-0">
              {editing ? (
                <>
                  <button
                    onClick={handleEditCancel}
                    className="px-4 py-2 border rounded hover:bg-gray-50"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving || !editForm.name.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    {saving ? '保存中...' : '保存'}
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className="px-4 py-2 border rounded hover:bg-gray-50"
                >
                  编辑任务
                </button>
              )}
              {(task.status === 'pending' || task.status === 'failed') && (
                <button
                  onClick={() => handleRun()}
                  disabled={editing}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                >
                  {task.status === 'failed' ? '重新运行' : '运行任务'}
                </button>
              )}
              <button
                onClick={handleDelete}
                disabled={editing}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                删除任务
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-6">
        <div className="bg-white rounded-lg shadow p-6">

          {datasetCustomTags.length > 0 && (
            <div className="mt-3">
              <h3 className="text-sm font-medium text-gray-700 mb-2">评测集自定义标签</h3>
              <div className="flex flex-wrap gap-2">
                {datasetCustomTags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {!editing && task.scoring_criteria && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="text-sm font-medium text-gray-700 mb-2">评分标准</h3>
              <p className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded">
                {task.scoring_criteria}
              </p>
            </div>
          )}

          {!editing && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Prompt</h3>
              <p className={`text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded ${task.prompt && !promptExpanded && shouldCollapsePrompt ? 'max-h-40 overflow-hidden' : ''}`}>
                {task.prompt || '未设置任务 Prompt'}
              </p>
              {task.prompt && shouldCollapsePrompt && (
                <button
                  onClick={() => setPromptExpanded((value) => !value)}
                  className="mt-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {promptExpanded ? '收起' : '展开'}
                </button>
              )}
            </div>
          )}

          {!editing && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="text-sm font-medium text-gray-700 mb-2">视频帧率</h3>
              <p className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded">
                {task.fps || 0.3}
              </p>
            </div>
          )}
          
          <div className="mt-4 pt-4 border-t text-sm text-gray-500">
            <span>创建时间: {new Date(task.created_at).toLocaleString('zh-CN')}</span>
            {task.completed_at && (
              <span className="ml-4">完成时间: {new Date(task.completed_at).toLocaleString('zh-CN')}</span>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold">评测结果 ({total}条)</h2>
              {resultsLoading && <p className="mt-1 text-sm text-gray-500">正在刷新结果列表...</p>}
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2">
                  <div className="text-xs text-blue-700">平均召回率</div>
                  <div className="text-lg font-semibold text-blue-900">
                    {formatNullableNumber(avgRecall, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-2">
                  <div className="text-xs text-green-700">平均准确率</div>
                  <div className="text-lg font-semibold text-green-900">
                    {formatNullableNumber(avgAccuracy, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-purple-200 bg-purple-50 px-4 py-2">
                  <div className="text-xs text-purple-700">平均输入 Tokens</div>
                  <div className="text-lg font-semibold text-purple-900">
                    {formatNullableNumber(avgInputTokens, 1)}
                  </div>
                </div>
                <div className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-2">
                  <div className="text-xs text-orange-700">平均输出 Tokens</div>
                  <div className="text-lg font-semibold text-orange-900">
                    {formatNullableNumber(avgOutputTokens, 1)}
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {task.status === 'running' && (
                <span className="text-sm text-blue-600">运行中，结果每 3 秒自动刷新</span>
              )}
              <div className="flex items-center gap-2">
                <label htmlFor="result-status-filter" className="text-sm text-gray-600">
                  任务运行状态
                </label>
                <select
                  id="result-status-filter"
                  value={resultStatusFilter}
                  onChange={(e) => {
                    setPage(1);
                    setResultStatusFilter(e.target.value as 'all' | TaskResultStatus);
                  }}
                  className="rounded border px-3 py-2 text-sm"
                >
                  <option value="all">全部</option>
                  <option value="pending">待运行</option>
                  <option value="running">运行中</option>
                  <option value="completed">已完成</option>
                  <option value="failed">失败</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="scoring-status-filter" className="text-sm text-gray-600">
                  评分状态
                </label>
                <select
                  id="scoring-status-filter"
                  value={scoringStatusFilter}
                  onChange={(e) => {
                    setPage(1);
                    setScoringStatusFilter(e.target.value as 'all' | TaskScoringStatus);
                  }}
                  className="rounded border px-3 py-2 text-sm"
                >
                  <option value="all">全部</option>
                  <option value="not_scored">未评分</option>
                  <option value="scoring">评分中</option>
                  <option value="scored">已评分</option>
                  <option value="score_failed">评分失败</option>
                </select>
              </div>
              {resultStatusFilter !== 'all' && (
                <button
                  type="button"
                  onClick={handleRunFiltered}
                  disabled={task.status === 'running' || total === 0}
                  className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:bg-gray-400"
                >
                  重新运行筛选结果
                </button>
              )}
              {scoringStatusFilter !== 'all' && (
                <button
                  type="button"
                  onClick={handleSmartScoreFiltered}
                  disabled={scoring || total === 0}
                  className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:bg-gray-400"
                >
                  智能评分筛选结果
                </button>
              )}
              <button
                type="button"
                onClick={() => handleSmartScore()}
                disabled={scoring || results.length === 0}
                className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:bg-gray-400"
              >
                {scoring ? '评分中...' : '智能评分'}
              </button>
            </div>
          </div>
        </div>
        
        {results.length === 0 ? (
          <div className="p-10 text-center text-gray-500">
            {task.status === 'pending' ? '请运行任务查看评测结果' : '当前筛选条件下暂无结果'}
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left">对象名称</th>
                  <th className="px-4 py-3 text-left">预览</th>
                  <th className="px-4 py-3 text-left">标注结果</th>
                  <th className="px-4 py-3 text-left">模型输出</th>
                  <th className="px-4 py-3 text-left">评分状态</th>
                  <th className="px-4 py-3 text-left">输入 Tokens</th>
                  <th className="px-4 py-3 text-left">输出 Tokens</th>
                  <th className="px-4 py-3 text-left">召回率</th>
                  <th className="px-4 py-3 text-left">准确率</th>
                  <th className="px-4 py-3 text-left">评分理由</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr key={result.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3">{result.file_name}</td>
                    <td className="px-4 py-3">
                      {result.download_url && (
                        <button
                          type="button"
                          onClick={() => openPreview(result)}
                          className="inline-flex h-16 w-16 items-center justify-center rounded border bg-gray-50 text-xs text-blue-600 hover:bg-blue-50 hover:text-blue-700"
                        >
                          {isVideo(result.file_type) ? '预览视频' : '预览图片'}
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {renderHoverText(result.ground_truth)}
                    </td>
                    <td className="px-4 py-3">
                      {renderHoverText(result.model_output || (result.status === 'running' ? '评测中...' : null))}
                    </td>
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        {getScoringStatusBadge(result.scoring_status)}
                        {result.scoring_status === 'score_failed' && result.scoring_error_message && (
                          <div className="max-w-xs">
                            {renderHoverText(result.scoring_error_message)}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600">
                        {result.input_tokens !== null ? result.input_tokens : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600">
                        {result.output_tokens !== null ? result.output_tokens : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600">
                        {result.recall !== null ? `${result.recall}%` : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600">
                        {result.accuracy !== null ? `${result.accuracy}%` : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      {renderHoverText(result.score_reason)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex justify-between items-center p-4 border-t">
              <div className="flex items-center space-x-2">
                <span className="text-gray-500 text-sm">共 {total} 条</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value) as 50 | 100); setPage(1); }}
                  className="px-2 py-1 border rounded text-sm"
                >
                  <option value={50}>50条/页</option>
                  <option value={100}>100条/页</option>
                </select>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1 border rounded text-sm disabled:bg-gray-100 disabled:text-gray-400"
                >
                  上一页
                </button>
                <span className="text-sm text-gray-500">
                  第 {page} / {totalPages} 页
                </span>
                <button
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1 border rounded text-sm disabled:bg-gray-100 disabled:text-gray-400"
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {showPreview && previewData && previewData.download_url && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={closePreview}>
          <div className="bg-white rounded-lg shadow-lg max-w-4xl max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">{previewData.file_name}</h3>
              <button onClick={closePreview} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>
            <div className="p-4 flex items-center justify-center" style={{ maxHeight: '70vh' }}>
              {isVideo(previewData.file_type) ? (
                <video src={previewData.download_url} className="max-w-full max-h-full" controls />
              ) : (
                <img src={previewData.download_url} alt={previewData.file_name} className="max-w-full max-h-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
