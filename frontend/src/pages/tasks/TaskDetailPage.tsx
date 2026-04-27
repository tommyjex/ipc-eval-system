import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { taskApi, datasetApi, promptTemplateApi, buildEvaluationDataPreviewUrl } from '../../api';
import type { EvaluationTask, TaskResultDetail, TaskStatus, TaskScoringStatus, TaskResultStatus, DatasetScene, PromptTemplate, PromptOptimizationResponse, PromptOptimizationVersionItem } from '../../api';

const getRecentPromptTemplateStorageKey = (scene: DatasetScene) => `recent-prompt-template:${scene}`;
const normalizeFps = (value: number) => Math.max(0.01, Math.min(30, Number(value.toFixed(2))));
const SMART_SCORE_DEFER_MS = 1500;
const SMART_SCORE_POLL_MS = 3000;
type MultiSelectOption<T extends string> = { value: T; label: string };
type MetricSortField = 'recall' | 'precision';
type MetricSortOrder = 'asc' | 'desc';
type MetricSortValue = '' | `${MetricSortField}:${MetricSortOrder}`;

const RESULT_STATUS_OPTIONS: MultiSelectOption<TaskResultStatus>[] = [
  { value: 'pending', label: '待运行' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];
const SCORING_STATUS_OPTIONS: MultiSelectOption<TaskScoringStatus>[] = [
  { value: 'not_scored', label: '未评分' },
  { value: 'scoring', label: '评分中' },
  { value: 'scored', label: '已评分' },
  { value: 'score_failed', label: '评分失败' },
];
const METRIC_SORT_OPTIONS: MultiSelectOption<MetricSortValue>[] = [
  { value: '', label: '默认' },
  { value: 'recall:desc', label: '降序' },
  { value: 'recall:asc', label: '升序' },
  { value: 'precision:desc', label: '降序' },
  { value: 'precision:asc', label: '升序' },
];
const formatNullableNumber = (value: number | null | undefined, digits = 1, suffix = '') =>
  (typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(digits)}${suffix}` : '-');
const formatVersionLabel = (version: PromptOptimizationVersionItem) =>
  `V${version.version_number} · ${new Date(version.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`;

const getMetricTrend = (
  baseline: number | null | undefined,
  current: number | null | undefined,
  betterDirection: 'higher' | 'lower' = 'higher',
) => {
  if (typeof baseline !== 'number' || typeof current !== 'number') {
    return { delta: null as number | null, label: '暂无对比', className: 'text-gray-500', arrow: '·' };
  }
  const delta = Number((current - baseline).toFixed(1));
  if (delta === 0) {
    return { delta, label: '持平', className: 'text-gray-500', arrow: '→' };
  }
  const improved = betterDirection === 'higher' ? delta > 0 : delta < 0;
  return {
    delta,
    label: improved ? '提升' : '下降',
    className: improved ? 'text-green-600' : 'text-red-600',
    arrow: improved ? '↑' : '↓',
  };
};
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
  precision: result.precision ?? null,
  score_reason: result.score_reason ?? null,
  tp_count: result.tp_count ?? null,
  fp_count: result.fp_count ?? null,
  fn_count: result.fn_count ?? null,
  ground_truth_unit_count: result.ground_truth_unit_count ?? null,
  predicted_unit_count: result.predicted_unit_count ?? null,
  is_scorable: result.is_scorable ?? null,
  is_empty_sample: result.is_empty_sample ?? null,
  empty_sample_passed: result.empty_sample_passed ?? null,
  metric_version: result.metric_version ?? null,
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
const getTaskResultPreviewUrl = (result: Pick<TaskResultDetail, 'data_id' | 'download_url' | 'file_type'>) =>
  buildEvaluationDataPreviewUrl(result.data_id);

const MultiSelectDropdown = <T extends string>({
  label,
  options,
  value,
  onChange,
  compact = false,
}: {
  label: string;
  options: MultiSelectOption<T>[];
  value: T[];
  onChange: (next: T[]) => void;
  compact?: boolean;
}) => {
  const [open, setOpen] = useState(false);
  const [draftValue, setDraftValue] = useState<T[]>(value);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      setDraftValue(value);
    }
  }, [value, open]);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) {
        setDraftValue(value);
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open, value]);

  const toggleOption = (optionValue: T) => {
    if (draftValue.includes(optionValue)) {
      setDraftValue(draftValue.filter((item) => item !== optionValue));
    } else {
      setDraftValue([...draftValue, optionValue]);
    }
  };
  const hasSelectedValue = value.length > 0;

  return (
    <div ref={panelRef} className={`relative ${compact ? '' : 'min-w-[160px]'}`}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex items-center text-xs font-normal ${
          hasSelectedValue ? 'text-orange-500 hover:text-orange-600' : 'text-gray-400 hover:text-gray-600'
        }`}
        aria-label={`筛选${label}`}
      >
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-2 w-56 rounded-md border bg-white p-2 shadow-lg">
          <div className="mb-2 flex items-center justify-between border-b pb-2">
            <span className="text-xs font-medium text-gray-700">{label}</span>
            <button
              type="button"
              onClick={() => {
                setDraftValue([]);
                onChange([]);
                setOpen(false);
              }}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              清空
            </button>
          </div>
          <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
            {options.map((option) => (
              <label key={option.value} className="flex cursor-pointer items-center gap-2 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={draftValue.includes(option.value)}
                  onChange={() => toggleOption(option.value)}
                  className="rounded border-gray-300"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-end gap-2 border-t pt-2">
            <button
              type="button"
              onClick={() => {
                setDraftValue(value);
                setOpen(false);
              }}
              className="rounded border px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => {
                onChange(draftValue);
                setOpen(false);
              }}
              className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
            >
              确定
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const SingleSelectDropdown = <T extends string>({
  label,
  options,
  value,
  onChange,
  highlighted,
  extraToggle,
}: {
  label: string;
  options: MultiSelectOption<T>[];
  value: T;
  onChange: (next: T) => void;
  highlighted?: boolean;
  extraToggle?: {
    label: string;
    checked: boolean;
    onToggle: () => void;
  };
}) => {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const hasSelectedValue = highlighted ?? value !== '';

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  const selectedLabel = options.find((option) => option.value === value)?.label ?? '默认';

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex items-center text-xs font-normal ${
          hasSelectedValue ? 'text-orange-500 hover:text-orange-600' : 'text-gray-400 hover:text-gray-600'
        }`}
        aria-label={label}
        title={`${label}: ${selectedLabel}`}
      >
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-2 w-40 rounded-md border bg-white p-1 shadow-lg">
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs ${
                  selected ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <span>{option.label}</span>
                <span>{selected ? '✓' : ''}</span>
              </button>
            );
          })}
          {extraToggle && (
            <>
              <div className="my-1 border-t" />
              <button
                type="button"
                onClick={extraToggle.onToggle}
                className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs ${
                  extraToggle.checked ? 'bg-orange-50 text-orange-700' : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <span>{extraToggle.label}</span>
                <span>{extraToggle.checked ? '✓' : ''}</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export const TaskDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<EvaluationTask | null>(null);
  const [datasetName, setDatasetName] = useState('');
  const [datasetScene, setDatasetScene] = useState<DatasetScene | null>(null);
  const [datasetCustomTags, setDatasetCustomTags] = useState<string[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [results, setResults] = useState<TaskResultDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');
  const [promptOptimizationError, setPromptOptimizationError] = useState('');
  const [promptOptimizationLoading, setPromptOptimizationLoading] = useState(false);
  const [promptOptimizationSaving, setPromptOptimizationSaving] = useState(false);
  const [promptOptimizationCompareLoading, setPromptOptimizationCompareLoading] = useState(false);
  const [promptOptimizationApplyLoading, setPromptOptimizationApplyLoading] = useState(false);
  const [promptOptimizationResult, setPromptOptimizationResult] = useState<PromptOptimizationResponse | null>(null);
  const [promptOptimizationVersions, setPromptOptimizationVersions] = useState<PromptOptimizationVersionItem[]>([]);
  const [selectedPromptOptimizationId, setSelectedPromptOptimizationId] = useState<number | null>(null);
  const [promptOptimizationDraft, setPromptOptimizationDraft] = useState('');
  const [promptOptimizationNotice, setPromptOptimizationNotice] = useState('');
  const [promptOptimizationNoticeTaskId, setPromptOptimizationNoticeTaskId] = useState<number | null>(null);
  const [promptOptimizationStage, setPromptOptimizationStage] = useState<1 | 2>(1);
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    prompt: '',
    fps: 0.3,
  });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState<50 | 100>(50);
  const [resultStatusFilter, setResultStatusFilter] = useState<TaskResultStatus[]>([]);
  const [scoringStatusFilter, setScoringStatusFilter] = useState<TaskScoringStatus[]>([]);
  const [metricSort, setMetricSort] = useState<MetricSortValue>('');
  const [emptySampleFailedOnly, setEmptySampleFailedOnly] = useState(false);
  const [microRecall, setMicroRecall] = useState<number | null>(null);
  const [microPrecision, setMicroPrecision] = useState<number | null>(null);
  const [macroRecall, setMacroRecall] = useState<number | null>(null);
  const [macroPrecision, setMacroPrecision] = useState<number | null>(null);
  const [coverageRate, setCoverageRate] = useState<number | null>(null);
  const [emptySamplePassRate, setEmptySamplePassRate] = useState<number | null>(null);
  const [unscorableCount, setUnscorableCount] = useState(0);
  const [avgInputTokens, setAvgInputTokens] = useState<number | null>(null);
  const [avgOutputTokens, setAvgOutputTokens] = useState<number | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<TaskResultDetail | null>(null);
  const [selectedPromptTemplateId, setSelectedPromptTemplateId] = useState('');
  const pollingRef = useRef(false);

  const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

  useEffect(() => {
    if (!promptOptimizationLoading) {
      setPromptOptimizationStage(1);
      return;
    }
    setPromptOptimizationStage(1);
    const timer = window.setTimeout(() => {
      setPromptOptimizationStage(2);
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [promptOptimizationLoading]);

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
            const promptTemplateRes = await promptTemplateApi.list({ scene: datasetRes.scene });
            setPromptTemplates(promptTemplateRes.items);
          } else {
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

  const fetchPromptOptimization = async (taskId: number, options?: { silent?: boolean }) => {
    try {
      const result = await taskApi.getPromptOptimization(taskId, {
        optimization_id: options?.silent ? selectedPromptOptimizationId ?? undefined : selectedPromptOptimizationId ?? undefined,
      });
      setPromptOptimizationResult(result);
      setSelectedPromptOptimizationId(result.optimization_id);
      setPromptOptimizationDraft(result.edited_prompt || result.optimized_prompt || '');
      if (!options?.silent) {
        setPromptOptimizationError('');
      }
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : '获取提示词优化结果失败';
      if (message.includes('暂无提示词优化结果')) {
        setPromptOptimizationResult(null);
        setPromptOptimizationDraft('');
        if (!options?.silent) {
          setPromptOptimizationError('');
        }
        return null;
      }
      if (!options?.silent) {
        setPromptOptimizationError(message);
      }
      return null;
    }
  };

  const fetchPromptOptimizationVersions = async (taskId: number) => {
    try {
      const result = await taskApi.listPromptOptimizations(taskId);
      setPromptOptimizationVersions(result.items);
      return result.items;
    } catch (err) {
      return [];
    }
  };

  const renderComparisonMetric = (
    label: string,
    baselineValue: number | null | undefined,
    currentValue: number | null | undefined,
    betterDirection: 'higher' | 'lower' = 'higher',
    suffix = '%',
  ) => {
    const trend = getMetricTrend(baselineValue, currentValue, betterDirection);
    return (
      <div className="rounded border border-gray-100 bg-gray-50 p-2">
        <div className="text-xs text-gray-500">{label}</div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="text-sm font-medium text-gray-800">{formatNullableNumber(currentValue, 1, suffix)}</div>
          <div className={`shrink-0 text-xs font-medium ${trend.className}`}>
            {trend.arrow} {trend.label}
            {trend.delta !== null ? ` ${Math.abs(trend.delta).toFixed(1)}${suffix}` : ''}
          </div>
        </div>
      </div>
    );
  };

  const renderStaticMetricCard = (
    label: string,
    value: number | null | undefined,
    suffix = '%',
  ) => (
    <div className="rounded border border-gray-100 bg-gray-50 p-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-gray-800">{formatNullableNumber(value, 1, suffix)}</div>
    </div>
  );

  const fetchResults = async (options?: { silent?: boolean }) => {
    if (!id) return;
    const silent = options?.silent ?? false;
    const [sortBy, sortOrder] = metricSort
      ? (metricSort.split(':') as [MetricSortField, MetricSortOrder])
      : [undefined, undefined];
    if (!silent) {
      setResultsLoading(true);
    }

    try {
      const resultsRes = await taskApi.getResultsDetail(parseInt(id), {
        page,
        page_size: pageSize,
        status: resultStatusFilter.length > 0 ? resultStatusFilter : undefined,
        scoring_status: scoringStatusFilter.length > 0 ? scoringStatusFilter : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        empty_sample_failed_only: emptySampleFailedOnly ? 1 : undefined,
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
      setMicroRecall(typeof resultsRes === 'object' && resultsRes !== null && 'micro_recall' in resultsRes && typeof resultsRes.micro_recall === 'number' ? resultsRes.micro_recall : null);
      setMicroPrecision(typeof resultsRes === 'object' && resultsRes !== null && 'micro_precision' in resultsRes && typeof resultsRes.micro_precision === 'number' ? resultsRes.micro_precision : null);
      setMacroRecall(typeof resultsRes === 'object' && resultsRes !== null && 'macro_recall' in resultsRes && typeof resultsRes.macro_recall === 'number' ? resultsRes.macro_recall : null);
      setMacroPrecision(typeof resultsRes === 'object' && resultsRes !== null && 'macro_precision' in resultsRes && typeof resultsRes.macro_precision === 'number' ? resultsRes.macro_precision : null);
      setCoverageRate(typeof resultsRes === 'object' && resultsRes !== null && 'coverage_rate' in resultsRes && typeof resultsRes.coverage_rate === 'number' ? resultsRes.coverage_rate : null);
      setEmptySamplePassRate(typeof resultsRes === 'object' && resultsRes !== null && 'empty_sample_pass_rate' in resultsRes && typeof resultsRes.empty_sample_pass_rate === 'number' ? resultsRes.empty_sample_pass_rate : null);
      setUnscorableCount(typeof resultsRes === 'object' && resultsRes !== null && 'unscorable_count' in resultsRes && typeof resultsRes.unscorable_count === 'number' ? resultsRes.unscorable_count : 0);
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

  const getScoringTotals = async (taskId: number) => {
    const [notScored, scoringInProgress, scored, scoreFailed] = await Promise.all([
      taskApi.getResultSelection(taskId, { scoring_status: ['not_scored'] }),
      taskApi.getResultSelection(taskId, { scoring_status: ['scoring'] }),
      taskApi.getResultSelection(taskId, { scoring_status: ['scored'] }),
      taskApi.getResultSelection(taskId, { scoring_status: ['score_failed'] }),
    ]);
    return {
      not_scored: notScored.total,
      scoring: scoringInProgress.total,
      scored: scored.total,
      score_failed: scoreFailed.total,
    };
  };

  const formatSmartScoreSummary = (result: { scored_count: number; failed_count: number; skipped_count: number }) => {
    if (result.scored_count > 0) {
      return `智能评分已完成，成功评分 ${result.scored_count} 条${result.failed_count > 0 ? `，失败 ${result.failed_count} 条` : ''}`;
    }
    if (result.failed_count > 0) {
      return `智能评分执行完成，但失败 ${result.failed_count} 条`;
    }
    return `没有可评分结果，已跳过 ${result.skipped_count} 条`;
  };

  const formatSmartScoreDiffSummary = (
    before: { not_scored: number; scoring: number; scored: number; score_failed: number },
    after: { not_scored: number; scoring: number; scored: number; score_failed: number },
  ) => {
    const scoredDelta = Math.max(0, after.scored - before.scored);
    const failedDelta = Math.max(0, after.score_failed - before.score_failed);
    const remaining = after.not_scored;
    if (scoredDelta > 0) {
      return `智能评分已完成，新增评分 ${scoredDelta} 条${failedDelta > 0 ? `，新增失败 ${failedDelta} 条` : ''}${remaining > 0 ? `，剩余未评分 ${remaining} 条` : ''}`;
    }
    if (failedDelta > 0) {
      return `智能评分执行完成，新增失败 ${failedDelta} 条${remaining > 0 ? `，剩余未评分 ${remaining} 条` : ''}`;
    }
    return remaining > 0 ? `智能评分已结束，当前仍有 ${remaining} 条未评分` : '智能评分已完成';
  };

  const waitForScoringToSettle = async (
    taskId: number,
    beforeTotals: { not_scored: number; scoring: number; scored: number; score_failed: number },
  ) => {
    let latestTotals = beforeTotals;
    for (let i = 0; i < 40; i += 1) {
      await delay(SMART_SCORE_POLL_MS);
      await fetchTaskInfo({ silent: true });
      await fetchResults({ silent: true });
      latestTotals = await getScoringTotals(taskId);
      if (latestTotals.scoring === 0) {
        return latestTotals;
      }
    }
    return latestTotals;
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
    setPromptOptimizationResult(null);
    setPromptOptimizationError('');
    setPromptOptimizationDraft('');
    setPromptOptimizationNotice('');
    setPromptOptimizationNoticeTaskId(null);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const taskId = parseInt(id, 10);
    void (async () => {
      const versions = await fetchPromptOptimizationVersions(taskId);
      if (versions.length > 0) {
        setSelectedPromptOptimizationId((prev) => prev ?? versions[0].optimization_id);
      } else {
        setSelectedPromptOptimizationId(null);
      }
    })();
  }, [id]);

  useEffect(() => {
    if (!id || selectedPromptOptimizationId == null) return;
    void fetchPromptOptimization(parseInt(id, 10), { silent: true });
  }, [id, selectedPromptOptimizationId]);

  useEffect(() => {
    if (!id || !promptOptimizationResult?.comparison) return;
    const compareStatus = promptOptimizationResult.comparison.compare_task.status;
    if (compareStatus !== 'pending' && compareStatus !== 'running') return;
    const timer = window.setInterval(() => {
      void fetchPromptOptimization(parseInt(id, 10), { silent: true });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [id, promptOptimizationResult?.compare_task_id, promptOptimizationResult?.comparison?.compare_task.status]);

  useEffect(() => {
    if (!id || loading) return;
    fetchResults();
  }, [id, page, pageSize, resultStatusFilter, scoringStatusFilter, metricSort, emptySampleFailedOnly, loading]);

  useEffect(() => {
    if (!saveSuccess) return;
    const timer = window.setTimeout(() => setSaveSuccess(''), 3000);
    return () => window.clearTimeout(timer);
  }, [saveSuccess]);

  useEffect(() => {
    if (task?.status !== 'pending' && task?.status !== 'running' && !scoring) return;
    const timer = window.setInterval(() => {
      fetchTaskInfo({ silent: true });
      fetchResults({ silent: true });
    }, SMART_SCORE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [task?.status, scoring, id, page, pageSize, resultStatusFilter, scoringStatusFilter, metricSort, emptySampleFailedOnly]);

  useEffect(() => {
    if (!editing || !datasetScene) {
      if (!editing) {
        setSelectedPromptTemplateId('');
      }
      return;
    }

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
  }, [editing, datasetScene, promptTemplates]);

  const handleRun = async (dataIds?: number[]) => {
    if (!id) return;
    try {
      await taskApi.run(parseInt(id), dataIds && dataIds.length > 0 ? { data_ids: dataIds } : undefined);
      setTask((prev) => (prev ? { ...prev, status: 'running' } : prev));
      setSaveSuccess('任务已启动，正在刷新结果列表');
      void fetchTaskInfo({ silent: true });
      void fetchResults({ silent: true });
    } catch (err) {
      alert('启动失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleRunFiltered = async () => {
    if (!id || resultStatusFilter.length === 0) return;
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
    const taskId = parseInt(id);
    try {
      const beforeTotals = await getScoringTotals(taskId);
      const scorePromise = taskApi.score(taskId, resultIds && resultIds.length > 0 ? { result_ids: resultIds } : undefined);
      const raceResult = await Promise.race([
        scorePromise.then((result) => ({ type: 'resolved' as const, result })),
        delay(SMART_SCORE_DEFER_MS).then(() => ({ type: 'deferred' as const })),
      ]);

      if (raceResult.type === 'resolved') {
        await fetchTaskInfo();
        await fetchResults({ silent: true });
        setSaveSuccess(formatSmartScoreSummary(raceResult.result));
        return;
      }

      setSaveSuccess('智能评分已发起，后台处理中，页面将自动刷新结果');

      try {
        const result = await scorePromise;
        await fetchTaskInfo({ silent: true });
        await fetchResults({ silent: true });
        setSaveSuccess(formatSmartScoreSummary(result));
      } catch (err) {
        const currentTotals = await getScoringTotals(taskId);
        const scoringLikelyStarted =
          currentTotals.scoring > 0 ||
          currentTotals.scored > beforeTotals.scored ||
          currentTotals.score_failed > beforeTotals.score_failed ||
          currentTotals.not_scored < beforeTotals.not_scored;

        if (!scoringLikelyStarted) {
          throw err;
        }

        const settledTotals = await waitForScoringToSettle(taskId, currentTotals);
        setSaveSuccess(formatSmartScoreDiffSummary(beforeTotals, settledTotals));
      }
    } catch (err) {
      alert('智能评分失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setScoring(false);
    }
  };

  const handleSmartScoreFiltered = async () => {
    if (!id || scoringStatusFilter.length === 0) return;
    setScoring(true);
    try {
      const selection = await taskApi.getResultSelection(parseInt(id), { scoring_status: scoringStatusFilter });
      if (selection.result_ids.length === 0) {
        setSaveSuccess('当前筛选条件下没有可评分结果');
        return;
      }
      await handleSmartScore(selection.result_ids);
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

  const getResultStatusBadge = (status: TaskResultStatus) => {
    const styles: Record<TaskResultStatus, string> = {
      pending: 'bg-gray-100 text-gray-800',
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    const labels: Record<TaskResultStatus, string> = {
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
  const canOptimizePrompt = task?.status === 'completed' && !editing && !scoring;

  const handleOptimizePrompt = async () => {
    if (!id) return;
    try {
      setPromptOptimizationLoading(true);
      setPromptOptimizationError('');
      setPromptOptimizationNotice('');
      setPromptOptimizationNoticeTaskId(null);
      setPromptOptimizationResult(null);
      const result = await taskApi.optimizePrompt(parseInt(id, 10));
      const versions = await fetchPromptOptimizationVersions(parseInt(id, 10));
      setSelectedPromptOptimizationId(result.optimization_id);
      setPromptOptimizationVersions(versions);
      setPromptOptimizationResult(result);
      setPromptOptimizationDraft(result.edited_prompt || result.optimized_prompt || '');
    } catch (err) {
      setPromptOptimizationError(err instanceof Error ? err.message : '提示词优化失败');
    } finally {
      setPromptOptimizationLoading(false);
    }
  };

  const savePromptOptimizationDraft = async () => {
    if (!id || !promptOptimizationResult) return null;
    try {
      setPromptOptimizationSaving(true);
      setPromptOptimizationError('');
      setPromptOptimizationNotice('');
      setPromptOptimizationNoticeTaskId(null);
      const result = await taskApi.updatePromptOptimization(parseInt(id, 10), {
        edited_prompt: promptOptimizationDraft.trim(),
      }, { optimization_id: selectedPromptOptimizationId ?? undefined });
      setPromptOptimizationResult(result);
      setPromptOptimizationDraft(result.edited_prompt || result.optimized_prompt || '');
      setPromptOptimizationNotice('已保存人工微调后的提示词');
      return result;
    } catch (err) {
      setPromptOptimizationError(err instanceof Error ? err.message : '保存优化后提示词失败');
      return null;
    } finally {
      setPromptOptimizationSaving(false);
    }
  };

  const ensurePromptOptimizationDraftSaved = async () => {
    if (!promptOptimizationResult) return null;
    const current = promptOptimizationDraft.trim();
    if (!current) {
      setPromptOptimizationError('优化后提示词不能为空');
      return null;
    }
    if (current === promptOptimizationResult.edited_prompt.trim()) {
      return promptOptimizationResult;
    }
    return savePromptOptimizationDraft();
  };

  const handleCreatePromptOptimizationCompareTask = async () => {
    if (!id || !promptOptimizationResult) return;
    const saved = await ensurePromptOptimizationDraftSaved();
    if (!saved) return;
    try {
      setPromptOptimizationCompareLoading(true);
      setPromptOptimizationError('');
      setPromptOptimizationNotice('');
      setPromptOptimizationNoticeTaskId(null);
      const result = await taskApi.createPromptOptimizationCompareTask(parseInt(id, 10), {
        optimization_id: selectedPromptOptimizationId ?? undefined,
      });
      await fetchPromptOptimizationVersions(parseInt(id, 10));
      setPromptOptimizationResult(result.optimization);
      setSelectedPromptOptimizationId(result.optimization.optimization_id);
      setPromptOptimizationDraft(result.optimization.edited_prompt || result.optimization.optimized_prompt || '');
      setPromptOptimizationNotice(`已创建对比任务：${result.compare_task.name}`);
      setPromptOptimizationNoticeTaskId(result.compare_task.id);
    } catch (err) {
      setPromptOptimizationError(err instanceof Error ? err.message : '创建对比任务失败');
    } finally {
      setPromptOptimizationCompareLoading(false);
    }
  };

  const handleApplyPromptOptimization = async () => {
    if (!id || !promptOptimizationResult) return;
    const saved = await ensurePromptOptimizationDraftSaved();
    if (!saved) return;
    try {
      setPromptOptimizationApplyLoading(true);
      setPromptOptimizationError('');
      setPromptOptimizationNotice('');
      setPromptOptimizationNoticeTaskId(null);
      const updatedTask = await taskApi.applyPromptOptimization(parseInt(id, 10), {
        optimization_id: selectedPromptOptimizationId ?? undefined,
      });
      setTask(updatedTask);
      setEditForm((prev) => ({ ...prev, prompt: updatedTask.prompt || '' }));
      setPromptOptimizationNotice('已将优化后提示词替换为当前任务 Prompt');
    } catch (err) {
      setPromptOptimizationError(err instanceof Error ? err.message : '替换任务 Prompt 失败');
    } finally {
      setPromptOptimizationApplyLoading(false);
    }
  };

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
              {!editing && (
                <button
                  onClick={handleOptimizePrompt}
                  disabled={!canOptimizePrompt || promptOptimizationLoading}
                  className="px-4 py-2 rounded border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:border-gray-200 disabled:bg-gray-100 disabled:text-gray-400"
                  title={canOptimizePrompt ? '基于当前任务全量已评分样本生成提示词优化建议' : '请先完成智能评分后再执行提示词优化'}
                >
                  {promptOptimizationLoading ? '优化中...' : '提示词优化'}
                </button>
              )}
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

          {!editing && promptOptimizationError && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-sm font-medium text-red-800">提示词优化失败</h3>
                  <p className="mt-1 text-sm text-red-700">{promptOptimizationError}</p>
                </div>
                <button
                  type="button"
                  onClick={handleOptimizePrompt}
                  disabled={promptOptimizationLoading || !canOptimizePrompt}
                  className="shrink-0 rounded border border-red-300 bg-white px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                >
                  重试
                </button>
              </div>
            </div>
          )}

          {!editing && promptOptimizationNotice && (
            <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm text-green-700">{promptOptimizationNotice}</div>
                {promptOptimizationNoticeTaskId && (
                  <button
                    type="button"
                    onClick={() => navigate(`/tasks/${promptOptimizationNoticeTaskId}`)}
                    className="shrink-0 text-sm font-medium text-green-700 hover:text-green-900 hover:underline"
                  >
                    打开新任务
                  </button>
                )}
              </div>
            </div>
          )}

          {!editing && promptOptimizationLoading && (
            <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 px-4 py-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 h-4 w-4 animate-spin rounded-full border-2 border-violet-300 border-t-violet-700" />
                <div>
                  <h3 className="text-sm font-medium text-violet-800">正在生成提示词优化建议</h3>
                  <p className="mt-1 text-sm text-violet-700">
                    当前会按“两阶段优化链路”依次完成问题分析、优化策略归纳和优化后提示词生成。
                  </p>
                  <div className="mt-3 space-y-0">
                    <div className="flex items-start gap-3">
                      <div className="flex flex-col items-center">
                        <div
                          className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium ${
                            promptOptimizationStage === 1
                              ? 'border-violet-600 bg-violet-600 text-white'
                              : 'border-green-600 bg-green-600 text-white'
                          }`}
                        >
                          {promptOptimizationStage === 1 ? '1' : '✓'}
                        </div>
                        <div className="mt-1 h-8 w-px bg-violet-200" />
                      </div>
                      <div className="pb-3">
                        <div className={`text-sm font-medium ${promptOptimizationStage >= 1 ? 'text-violet-900' : 'text-gray-500'}`}>
                          阶段 1 / 2
                        </div>
                        <div className={`text-sm ${promptOptimizationStage === 1 ? 'text-violet-700' : 'text-gray-600'}`}>
                          分析问题并归纳优化策略
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="flex flex-col items-center">
                        <div
                          className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium ${
                            promptOptimizationStage === 2
                              ? 'border-violet-600 bg-violet-600 text-white'
                              : 'border-violet-300 bg-white text-violet-400'
                          }`}
                        >
                          {promptOptimizationStage === 2 ? '2' : '○'}
                        </div>
                      </div>
                      <div>
                        <div className={`text-sm font-medium ${promptOptimizationStage === 2 ? 'text-violet-900' : 'text-gray-500'}`}>
                          阶段 2 / 2
                        </div>
                        <div className={`text-sm ${promptOptimizationStage === 2 ? 'text-violet-700' : 'text-gray-600'}`}>
                          生成优化后提示词
                        </div>
                      </div>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-violet-600">
                    大任务会基于全量已评分样本进行分析，耗时可能明显增加，请耐心等待。
                  </p>
                </div>
              </div>
            </div>
          )}

          {!editing && !promptOptimizationLoading && !promptOptimizationError && !promptOptimizationResult && (
            <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-5">
              <h3 className="text-sm font-medium text-gray-800">提示词优化</h3>
              <p className="mt-1 text-sm text-gray-600">
                基于当前任务的全量已评分样本，重点分析标注结果与模型输出的 diff，输出问题摘要、优化策略和一版优化后提示词。
              </p>
              <p className="mt-2 text-xs text-gray-500">
                仅对已完成智能评分的任务开放；点击右上角“提示词优化”即可开始生成。
              </p>
            </div>
          )}

          {!editing && promptOptimizationResult && (
            <div className="mt-4 pt-4 border-t">
              <div className="mb-3 flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-700">提示词优化结果</h3>
                  <p className="mt-1 text-xs text-gray-500">
                    版本 V{promptOptimizationResult.version_number} · 基于 {promptOptimizationResult.sample_count} 条已评分样本，模型 {promptOptimizationResult.optimization_model}
                  </p>
                </div>
                <div />
              </div>
              <div className="space-y-4">
                {promptOptimizationVersions.length > 0 && (
                  <div className="rounded bg-white p-4 border">
                    <div className="mb-2 text-sm font-medium text-gray-800">历史版本</div>
                    <div className="flex flex-wrap gap-2">
                      {promptOptimizationVersions.map((version) => {
                        const selected = version.optimization_id === selectedPromptOptimizationId;
                        return (
                          <button
                            key={version.optimization_id}
                            type="button"
                            onClick={() => {
                              setPromptOptimizationNotice('');
                              setPromptOptimizationError('');
                              setSelectedPromptOptimizationId(version.optimization_id);
                            }}
                            className={`rounded border px-3 py-1.5 text-sm ${
                              selected
                                ? 'border-violet-600 bg-violet-50 text-violet-700'
                                : 'border-gray-200 bg-gray-50 text-gray-700 hover:bg-gray-100'
                            }`}
                          >
                            {formatVersionLabel(version)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
                <div className="rounded bg-violet-50 p-4">
                  <div className="mb-2 text-sm font-medium text-violet-800">问题摘要</div>
                  <p className="whitespace-pre-wrap text-sm text-violet-900">{promptOptimizationResult.analysis_summary}</p>
                </div>
                <div className="rounded bg-gray-50 p-4">
                  <div className="mb-2 text-sm font-medium text-gray-800">问题点</div>
                  {promptOptimizationResult.issues.length > 0 ? (
                    <div className="space-y-3">
                      {promptOptimizationResult.issues.map((issue, index) => (
                        <div key={`${issue.title}-${index}`} className="rounded border bg-white p-3">
                          <div className="text-sm font-medium text-gray-900">{issue.title}</div>
                          <div className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{issue.summary}</div>
                          {issue.evidence.length > 0 && (
                            <div className="mt-2 text-xs text-gray-500">
                              证据样本：{issue.evidence.join('；')}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-gray-500">模型未返回结构化问题点列表。</div>
                  )}
                </div>
                <div className="rounded bg-green-50 p-4">
                  <div className="mb-2 text-sm font-medium text-green-800">优化策略</div>
                  {promptOptimizationResult.optimization_strategies.length > 0 ? (
                    <ul className="space-y-1 text-sm text-green-900">
                      {promptOptimizationResult.optimization_strategies.map((strategy, index) => (
                        <li key={`${strategy}-${index}`}>• {strategy}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-sm text-green-900">模型未返回结构化优化策略列表。</div>
                  )}
                </div>
                <div className="rounded bg-blue-50 p-4">
                  <div className="mb-2 text-sm font-medium text-blue-800">优化后提示词</div>
                  <div className="flex flex-col gap-4 lg:flex-row">
                    <div className="flex-1">
                      <textarea
                        value={promptOptimizationDraft}
                        onChange={(event) => setPromptOptimizationDraft(event.target.value)}
                        rows={12}
                        className="w-full rounded border border-blue-100 bg-white p-3 text-sm text-gray-800"
                        placeholder="可在此基础上继续人工微调优化后的提示词"
                      />
                      <p className="mt-2 text-xs text-blue-700">
                        你可以继续人工微调，然后选择保存、创建对比任务，或直接替换为当前任务 Prompt。
                      </p>
                    </div>
                    <div className="flex w-full shrink-0 flex-col gap-2 lg:w-56">
                      <button
                        type="button"
                        onClick={savePromptOptimizationDraft}
                        disabled={promptOptimizationSaving || promptOptimizationCompareLoading || promptOptimizationApplyLoading || !promptOptimizationDraft.trim()}
                        className="rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-400"
                      >
                        {promptOptimizationSaving ? '保存中...' : '保存微调'}
                      </button>
                      <button
                        type="button"
                        onClick={handleCreatePromptOptimizationCompareTask}
                        disabled={promptOptimizationSaving || promptOptimizationCompareLoading || promptOptimizationApplyLoading || !promptOptimizationDraft.trim()}
                        className="rounded bg-violet-600 px-3 py-2 text-sm text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                      >
                        {promptOptimizationCompareLoading ? '创建中...' : '新建对比任务并运行评分'}
                      </button>
                      <button
                        type="button"
                        onClick={handleApplyPromptOptimization}
                        disabled={promptOptimizationSaving || promptOptimizationCompareLoading || promptOptimizationApplyLoading || !promptOptimizationDraft.trim()}
                        className="rounded border border-blue-200 bg-blue-100 px-3 py-2 text-sm text-blue-700 hover:bg-blue-200 disabled:cursor-not-allowed disabled:border-gray-200 disabled:bg-gray-100 disabled:text-gray-400"
                      >
                        {promptOptimizationApplyLoading ? '替换中...' : '替换为任务 Prompt'}
                      </button>
                      <button
                        type="button"
                        onClick={() => navigator.clipboard.writeText(promptOptimizationDraft || promptOptimizationResult.edited_prompt || promptOptimizationResult.optimized_prompt)}
                        className="rounded border border-transparent px-3 py-2 text-sm text-blue-600 hover:bg-white hover:text-blue-800"
                      >
                        复制当前提示词
                      </button>
                    </div>
                  </div>
                </div>
                {promptOptimizationResult.revision_summary.length > 0 && (
                  <div className="rounded bg-amber-50 p-4">
                    <div className="mb-2 text-sm font-medium text-amber-800">修改说明</div>
                    <ul className="space-y-1 text-sm text-amber-900">
                      {promptOptimizationResult.revision_summary.map((item, index) => (
                        <li key={`${item}-${index}`}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {promptOptimizationResult.comparison && (
                  <div className="rounded bg-slate-50 p-4">
                    <div className="mb-3 flex items-center justify-between gap-4">
                      <div className="text-sm font-medium text-slate-800">优化前后效果对比</div>
                      <div className="text-xs text-slate-500">
                        对比任务状态：{getStatusBadge(promptOptimizationResult.comparison.compare_task.status)}
                      </div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded border bg-white p-4">
                        <div className="mb-2 text-sm font-medium text-gray-900">优化前</div>
                        <div className="text-xs text-gray-500">{promptOptimizationResult.comparison.baseline_task.task_name}</div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-gray-700">
                          {renderStaticMetricCard('Micro 召回率', promptOptimizationResult.comparison.baseline_task.micro_recall)}
                          {renderStaticMetricCard('Micro 精确率', promptOptimizationResult.comparison.baseline_task.micro_precision)}
                          {renderStaticMetricCard('Macro 召回率', promptOptimizationResult.comparison.baseline_task.macro_recall)}
                          {renderStaticMetricCard('Macro 精确率', promptOptimizationResult.comparison.baseline_task.macro_precision)}
                          {renderStaticMetricCard('覆盖率', promptOptimizationResult.comparison.baseline_task.coverage_rate)}
                          {renderStaticMetricCard('空样本通过率', promptOptimizationResult.comparison.baseline_task.empty_sample_pass_rate)}
                          {renderStaticMetricCard('不可评分数', promptOptimizationResult.comparison.baseline_task.unscorable_count, '')}
                        </div>
                      </div>
                      <div className="rounded border bg-white p-4">
                        <div className="mb-2 text-sm font-medium text-gray-900">优化后</div>
                        <div className="text-xs text-gray-500">{promptOptimizationResult.comparison.compare_task.task_name}</div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-gray-700">
                          {renderComparisonMetric('Micro 召回率', promptOptimizationResult.comparison.baseline_task.micro_recall, promptOptimizationResult.comparison.compare_task.micro_recall)}
                          {renderComparisonMetric('Micro 精确率', promptOptimizationResult.comparison.baseline_task.micro_precision, promptOptimizationResult.comparison.compare_task.micro_precision)}
                          {renderComparisonMetric('Macro 召回率', promptOptimizationResult.comparison.baseline_task.macro_recall, promptOptimizationResult.comparison.compare_task.macro_recall)}
                          {renderComparisonMetric('Macro 精确率', promptOptimizationResult.comparison.baseline_task.macro_precision, promptOptimizationResult.comparison.compare_task.macro_precision)}
                          {renderComparisonMetric('覆盖率', promptOptimizationResult.comparison.baseline_task.coverage_rate, promptOptimizationResult.comparison.compare_task.coverage_rate)}
                          {renderComparisonMetric('空样本通过率', promptOptimizationResult.comparison.baseline_task.empty_sample_pass_rate, promptOptimizationResult.comparison.compare_task.empty_sample_pass_rate)}
                          {renderComparisonMetric('不可评分数', promptOptimizationResult.comparison.baseline_task.unscorable_count, promptOptimizationResult.comparison.compare_task.unscorable_count, 'lower', '')}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
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
                  <div className="text-xs text-blue-700">Micro 召回率</div>
                  <div className="text-lg font-semibold text-blue-900">
                    {formatNullableNumber(microRecall, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-2">
                  <div className="text-xs text-green-700">Micro 精确率</div>
                  <div className="text-lg font-semibold text-green-900">
                    {formatNullableNumber(microPrecision, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2">
                  <div className="text-xs text-emerald-700">Macro 召回率</div>
                  <div className="text-lg font-semibold text-emerald-900">
                    {formatNullableNumber(macroRecall, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-2">
                  <div className="text-xs text-teal-700">Macro 精确率</div>
                  <div className="text-lg font-semibold text-teal-900">
                    {formatNullableNumber(macroPrecision, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-2">
                  <div className="text-xs text-cyan-700">覆盖率</div>
                  <div className="text-lg font-semibold text-cyan-900">
                    {formatNullableNumber(coverageRate, 1, '%')}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2">
                  <div className="text-xs text-slate-700">空样本通过率</div>
                  <div className="text-lg font-semibold text-slate-900">
                    {formatNullableNumber(emptySamplePassRate, 1, '%')}
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
              <p className="mt-3 text-xs text-gray-500">
                汇总指标默认采用 Micro 口径；空样本不计入主指标聚合，不可评测样本当前为 {unscorableCount} 条。
              </p>
            </div>
            <div className="flex items-center gap-4">
              {task.status === 'running' && (
                <span className="text-sm text-blue-600">运行中，结果每 3 秒自动刷新</span>
              )}
              {resultStatusFilter.length > 0 && (
                <button
                  type="button"
                  onClick={handleRunFiltered}
                  disabled={task.status === 'running' || total === 0}
                  className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:bg-gray-400"
                >
                  重新运行筛选结果
                </button>
              )}
              {scoringStatusFilter.length > 0 && (
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
        
        <div className="overflow-x-auto">
          <table className="min-w-[1500px] w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">对象名称</th>
                <th className="px-4 py-3 text-left">预览</th>
                <th className="px-4 py-3 text-left">标注结果</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">
                  <div className="flex items-center gap-2 whitespace-nowrap">
                    <span className="whitespace-nowrap">评测状态</span>
                    <MultiSelectDropdown
                      label="评测状态"
                      options={RESULT_STATUS_OPTIONS}
                      value={resultStatusFilter}
                      compact
                      onChange={(next) => {
                        setPage(1);
                        setResultStatusFilter(next);
                      }}
                    />
                  </div>
                </th>
                <th className="px-4 py-3 text-left">模型输出</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">
                  <div className="flex items-center gap-2 whitespace-nowrap">
                    <span className="whitespace-nowrap">评分状态</span>
                    <MultiSelectDropdown
                      label="评分状态"
                      options={SCORING_STATUS_OPTIONS}
                      value={scoringStatusFilter}
                      compact
                      onChange={(next) => {
                        setPage(1);
                        setScoringStatusFilter(next);
                      }}
                    />
                  </div>
                </th>
                <th className="px-4 py-3 text-left whitespace-nowrap">输入 Tokens</th>
                <th className="px-4 py-3 text-left whitespace-nowrap">输出 Tokens</th>
                <th className="px-4 py-3 text-left whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <span>召回率</span>
                    <SingleSelectDropdown
                      label="召回率排序"
                      options={[
                        METRIC_SORT_OPTIONS[0],
                        METRIC_SORT_OPTIONS[1],
                        METRIC_SORT_OPTIONS[2],
                      ]}
                      highlighted={metricSort.startsWith('recall:') || emptySampleFailedOnly}
                      extraToggle={{
                        label: '空样本未通过',
                        checked: emptySampleFailedOnly,
                        onToggle: () => {
                          setPage(1);
                          setEmptySampleFailedOnly((prev) => !prev);
                        },
                      }}
                      value={metricSort.startsWith('recall:') ? metricSort : ''}
                      onChange={(next) => {
                        setPage(1);
                        setMetricSort(next);
                      }}
                    />
                  </div>
                </th>
                <th className="px-4 py-3 text-left whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <span>精确率</span>
                    <SingleSelectDropdown
                      label="精确率排序"
                      options={[
                        METRIC_SORT_OPTIONS[0],
                        METRIC_SORT_OPTIONS[3],
                        METRIC_SORT_OPTIONS[4],
                      ]}
                      highlighted={metricSort.startsWith('precision:')}
                      value={metricSort.startsWith('precision:') ? metricSort : ''}
                      onChange={(next) => {
                        setPage(1);
                        setMetricSort(next);
                      }}
                    />
                  </div>
                </th>
                <th className="px-4 py-3 text-left">评分理由</th>
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr>
                  <td colSpan={11} className="p-10 text-center text-gray-500">
                    {task.status === 'pending' ? '请运行任务查看评测结果' : '当前筛选条件下暂无结果'}
                  </td>
                </tr>
              ) : (
                results.map((result) => (
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
                      <div className="space-y-1">
                        {getResultStatusBadge(result.status)}
                        {result.status === 'failed' && result.error_message && (
                          <div className="max-w-xs">
                            {renderHoverText(result.error_message)}
                          </div>
                        )}
                      </div>
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
                        {result.precision !== null ? `${result.precision}%` : '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      {renderHoverText(result.score_reason)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

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
      </div>

      {showPreview && previewData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={closePreview}>
          <div className="bg-white rounded-lg shadow-lg max-w-4xl max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">{previewData.file_name}</h3>
              <button onClick={closePreview} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>
            <div className="p-4 flex items-center justify-center" style={{ maxHeight: '70vh' }}>
              {isVideo(previewData.file_type) ? (
                <video src={getTaskResultPreviewUrl(previewData)} className="max-w-full max-h-full" controls />
              ) : (
                <img src={getTaskResultPreviewUrl(previewData)} alt={previewData.file_name} className="max-w-full max-h-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
