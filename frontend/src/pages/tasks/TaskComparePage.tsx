import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { datasetApi, taskApi } from '../../api';
import type { Dataset, EvaluationTask } from '../../api';

const formatMetric = (value: number | null) => (value == null ? '-' : `${value.toFixed(2)}%`);
const formatTokenMetric = (value: number | null) => (value == null ? '-' : value.toFixed(2));
type MultiSelectOption = { value: string; label: string };

const getBarHeight = (value: number | null) => `${Math.max(0, Math.min(100, value ?? 0))}%`;
const truncateLabel = (value: string, maxLength: number) => (value.length > maxLength ? `${value.slice(0, maxLength)}...` : value);

const getRankedBarClass = (
  index: number,
  total: number,
  palette: {
    top: string;
    high: string;
    medium: string;
    low: string;
  },
) => {
  if (total <= 1 || index === 0) return palette.top;
  const ratio = index / Math.max(total - 1, 1);
  if (ratio <= 0.33) return palette.high;
  if (ratio <= 0.66) return palette.medium;
  return palette.low;
};

const describePercentageDelta = (current: number | null, baseline: number | null, label: string) => {
  if (current == null || baseline == null || baseline === 0) {
    return `${label}暂无可比数据`;
  }
  const delta = ((current - baseline) / baseline) * 100;
  if (Math.abs(delta) < 0.01) {
    return `${label}基本持平`;
  }
  return delta > 0
    ? `${label}高 ${Math.abs(delta).toFixed(1)}%`
    : `${label}少 ${Math.abs(delta).toFixed(1)}%`;
};

const VerticalMetricChart: React.FC<{
  title: string;
  description: string;
  tasks: EvaluationTask[];
  metricKey: 'avg_recall' | 'avg_accuracy';
  colorPalette: {
    top: string;
    high: string;
    medium: string;
    low: string;
  };
  accentClass: string;
}> = ({ title, description, tasks, metricKey, colorPalette, accentClass }) => (
  <div className="rounded-lg bg-white p-4 shadow">
    <div className="mb-4">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <p className="mt-1 text-sm text-gray-600">{description}</p>
    </div>
    <div className="overflow-x-auto">
      <div className="min-w-[720px]">
        <div className="flex h-80 items-end gap-3 border-b border-l border-gray-200 px-4 pb-4 pt-6">
          {tasks.map((task, index) => {
            const value = task[metricKey];
            const barClass = getRankedBarClass(index, tasks.length, colorPalette);
            return (
              <div key={`${metricKey}-${task.id}`} className="group flex min-w-[104px] flex-1 flex-col items-center justify-end">
                <div className="relative flex h-56 w-full items-end justify-center">
                  <div className="pointer-events-none absolute -top-20 left-1/2 z-10 hidden w-56 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg group-hover:block">
                    <div className="font-medium">{task.name}</div>
                    <div className="mt-1 text-gray-200">{task.target_model}</div>
                    <div className="mt-2 font-semibold text-white">{title}：{formatMetric(value)}</div>
                  </div>
                  <div
                    className={`w-full max-w-[64px] rounded-t-md transition-all duration-200 group-hover:opacity-90 ${barClass}`}
                    style={{ height: getBarHeight(value) }}
                  />
                </div>
                <div className={`mt-2 text-sm font-medium ${accentClass}`}>{formatMetric(value)}</div>
                <div className="mt-2 text-center text-[11px] leading-4 text-gray-600">
                  <div className="font-medium text-gray-800" title={task.name}>{truncateLabel(task.name, 12)}</div>
                  <div title={task.target_model}>{truncateLabel(task.target_model, 14)}</div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="px-4 pt-2 text-right text-xs text-gray-500">纵轴：得分（%）</div>
      </div>
    </div>
  </div>
);

const MultiSelectDropdown: React.FC<{
  label: string;
  options: MultiSelectOption[];
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}> = ({ label, options, value, onChange, disabled = false }) => {
  const [open, setOpen] = useState(false);
  const [draftValue, setDraftValue] = useState<string[]>(value);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const hasSelectedValue = value.length > 0;
  const selectedText = value.length > 0 ? value.join('、') : `全部${label}`;

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

  const toggleOption = (optionValue: string) => {
    if (draftValue.includes(optionValue)) {
      setDraftValue(draftValue.filter((item) => item !== optionValue));
    } else {
      setDraftValue([...draftValue, optionValue]);
    }
  };

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        disabled={disabled}
        className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-sm ${
          disabled
            ? 'cursor-not-allowed bg-gray-50 text-gray-300'
            : hasSelectedValue
              ? 'border-orange-300 text-gray-700 hover:border-orange-400'
              : 'border-gray-300 text-gray-700 hover:border-gray-400'
        }`}
        aria-label={`筛选${label}`}
      >
        <span className="truncate">{selectedText}</span>
        <span className={`ml-3 shrink-0 ${hasSelectedValue ? 'text-orange-500' : 'text-gray-400'}`}>
          {open ? '▲' : '▼'}
        </span>
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

export const TaskComparePage: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [completedTasks, setCompletedTasks] = useState<EvaluationTask[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [datasetRes, taskRes] = await Promise.all([
          datasetApi.list({ page: 1, page_size: 100 }),
          taskApi.list({ status: ['completed'], page: 1, page_size: 100 }),
        ]);
        setDatasets(datasetRes.items);
        setCompletedTasks(taskRes.items);
        if (datasetRes.items.length > 0) {
          const availableDatasetIds = new Set(taskRes.items.map((task) => String(task.dataset_id)));
          const firstDataset = datasetRes.items.find((dataset) => availableDatasetIds.has(String(dataset.id)));
          if (firstDataset) {
            setSelectedDatasetId(String(firstDataset.id));
          }
        }
      } catch (error) {
        console.error('加载对比分析数据失败:', error);
        setDatasets([]);
        setCompletedTasks([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const groupedTasks = useMemo(() => {
    if (!selectedDatasetId) return [];
    return completedTasks.filter(
      (task) =>
        String(task.dataset_id) === selectedDatasetId &&
        (selectedModels.length === 0 || selectedModels.includes(task.target_model)),
    );
  }, [completedTasks, selectedDatasetId, selectedModels]);

  const availableModels = useMemo(() => {
    if (!selectedDatasetId) return [];
    return Array.from(
      new Set(
        completedTasks
          .filter((task) => String(task.dataset_id) === selectedDatasetId)
          .map((task) => task.target_model),
      ),
    )
      .sort()
      .map((model) => ({ value: model, label: model }));
  }, [completedTasks, selectedDatasetId]);

  const bestRecall = useMemo(
    () => Math.max(...groupedTasks.map((task) => task.avg_recall ?? -1), -1),
    [groupedTasks],
  );
  const bestAccuracy = useMemo(
    () => Math.max(...groupedTasks.map((task) => task.avg_accuracy ?? -1), -1),
    [groupedTasks],
  );

  const recallSortedTasks = useMemo(
    () =>
      [...groupedTasks].sort(
        (a, b) => (b.avg_recall ?? -1) - (a.avg_recall ?? -1) || a.created_at.localeCompare(b.created_at),
      ),
    [groupedTasks],
  );

  const accuracySortedTasks = useMemo(
    () =>
      [...groupedTasks].sort(
        (a, b) => (b.avg_accuracy ?? -1) - (a.avg_accuracy ?? -1) || a.created_at.localeCompare(b.created_at),
      ),
    [groupedTasks],
  );

  const modelTokenSummaries = useMemo(() => {
    const modelMap = new Map<string, { model: string; inputValues: number[]; outputValues: number[] }>();
    groupedTasks.forEach((task) => {
      const current = modelMap.get(task.target_model) ?? {
        model: task.target_model,
        inputValues: [],
        outputValues: [],
      };
      if (task.avg_input_tokens != null) current.inputValues.push(task.avg_input_tokens);
      if (task.avg_output_tokens != null) current.outputValues.push(task.avg_output_tokens);
      modelMap.set(task.target_model, current);
    });

    return Array.from(modelMap.values()).map((item) => ({
      model: item.model,
      avgInputTokens:
        item.inputValues.length > 0
          ? item.inputValues.reduce((sum, value) => sum + value, 0) / item.inputValues.length
          : null,
      avgOutputTokens:
        item.outputValues.length > 0
          ? item.outputValues.reduce((sum, value) => sum + value, 0) / item.outputValues.length
          : null,
    }));
  }, [groupedTasks]);

  const tokenComparisonConclusions = useMemo(() => {
    const conclusions: string[] = [];
    for (let i = 0; i < modelTokenSummaries.length; i += 1) {
      for (let j = i + 1; j < modelTokenSummaries.length; j += 1) {
        const current = modelTokenSummaries[i];
        const baseline = modelTokenSummaries[j];
        conclusions.push(
          `${current.model} 比 ${baseline.model}，${describePercentageDelta(
            current.avgInputTokens,
            baseline.avgInputTokens,
            '输入 Token',
          )}，${describePercentageDelta(current.avgOutputTokens, baseline.avgOutputTokens, '输出 Token')}。`,
        );
      }
    }
    return conclusions;
  }, [modelTokenSummaries]);

  const selectedDatasetName =
    datasets.find((dataset) => String(dataset.id) === selectedDatasetId)?.name ?? '未选择评测集';

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="mb-2">
            <Link to="/tasks" className="text-sm text-blue-600 hover:text-blue-800 hover:underline">
              返回评测任务
            </Link>
          </div>
          <h1 className="text-2xl font-bold">对比分析</h1>
          <p className="mt-2 text-sm text-gray-600">仅支持同一个评测集下不同已完成评测任务的结果对比。</p>
        </div>
      </div>

      <div className="mb-6 rounded-lg bg-white p-4 shadow">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="compare-dataset" className="mb-2 block text-sm font-medium text-gray-700">
              评测集
            </label>
            <select
              id="compare-dataset"
              value={selectedDatasetId}
              onChange={(e) => {
                setSelectedDatasetId(e.target.value);
                setSelectedModels([]);
              }}
              className="w-full rounded border px-3 py-2 text-sm"
            >
              <option value="">请选择评测集</option>
              {datasets
                .filter((dataset) => completedTasks.some((task) => task.dataset_id === dataset.id))
                .map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">模型</label>
            <MultiSelectDropdown
              label="模型"
              options={availableModels}
              value={selectedModels}
              onChange={setSelectedModels}
              disabled={!selectedDatasetId}
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-10 text-center">加载中...</div>
      ) : !selectedDatasetId ? (
        <div className="rounded-lg bg-white p-10 text-center text-gray-500 shadow">当前暂无可对比的评测集</div>
      ) : groupedTasks.length < 2 ? (
        <div className="rounded-lg bg-white p-10 text-center text-gray-500 shadow">
          评测集“{selectedDatasetName}”下已完成任务不足 2 个，暂无法对比。
        </div>
      ) : (
        <div className="space-y-6">
          <VerticalMetricChart
            title="召回率柱状图"
            description="按召回率从高到低排列，横轴为任务（任务名 + 模型），纵轴为得分。"
            tasks={recallSortedTasks}
            metricKey="avg_recall"
            colorPalette={{
              top: 'bg-green-700',
              high: 'bg-green-600',
              medium: 'bg-green-500',
              low: 'bg-green-300',
            }}
            accentClass="text-green-700"
          />

          <VerticalMetricChart
            title="准确率柱状图"
            description="按准确率从高到低排列，横轴为任务（任务名 + 模型），纵轴为得分。"
            tasks={accuracySortedTasks}
            metricKey="avg_accuracy"
            colorPalette={{
              top: 'bg-orange-700',
              high: 'bg-orange-600',
              medium: 'bg-orange-500',
              low: 'bg-orange-300',
            }}
            accentClass="text-orange-600"
          />

          <div className="rounded-lg bg-white p-4 shadow">
            <h2 className="text-lg font-semibold text-gray-900">Token 对比分析</h2>
            <p className="mt-1 text-sm text-gray-600">按模型聚合各任务的平均输入 / 输出 Token，并生成差异结论。</p>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-[640px] w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left">模型</th>
                    <th className="px-4 py-3 text-left">平均输入 Token</th>
                    <th className="px-4 py-3 text-left">平均输出 Token</th>
                  </tr>
                </thead>
                <tbody>
                  {modelTokenSummaries.map((item) => (
                    <tr key={item.model} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{item.model}</td>
                      <td className="px-4 py-3">{formatTokenMetric(item.avgInputTokens)}</td>
                      <td className="px-4 py-3">{formatTokenMetric(item.avgOutputTokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 space-y-2">
              {tokenComparisonConclusions.length === 0 ? (
                <div className="rounded border border-dashed border-gray-300 bg-gray-50 px-4 py-3 text-sm text-gray-500">
                  当前模型数量不足 2 个，或缺少可比较的 Token 数据。
                </div>
              ) : (
                tokenComparisonConclusions.map((conclusion) => (
                  <div key={conclusion} className="rounded border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
                    {conclusion}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-lg bg-white shadow overflow-x-auto">
            <table className="min-w-[1200px] w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left">任务名称</th>
                  <th className="px-4 py-3 text-left">模型供应商</th>
                  <th className="px-4 py-3 text-left">目标模型</th>
                  <th className="px-4 py-3 text-left">平均召回率</th>
                  <th className="px-4 py-3 text-left">平均准确率</th>
                  <th className="px-4 py-3 text-left">平均输入 Token</th>
                  <th className="px-4 py-3 text-left">平均输出 Token</th>
                  <th className="px-4 py-3 text-left">结论</th>
                </tr>
              </thead>
              <tbody>
                {groupedTasks.map((task) => {
                  const isBestRecall = task.avg_recall != null && task.avg_recall === bestRecall;
                  const isBestAccuracy = task.avg_accuracy != null && task.avg_accuracy === bestAccuracy;
                  return (
                    <tr key={task.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <Link to={`/tasks/${task.id}`} className="text-blue-600 hover:text-blue-800 hover:underline">
                          {task.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3">{task.model_provider}</td>
                      <td className="px-4 py-3">{task.target_model}</td>
                      <td className={`px-4 py-3 ${isBestRecall ? 'font-semibold text-green-700' : ''}`}>
                        {formatMetric(task.avg_recall)}
                      </td>
                      <td className={`px-4 py-3 ${isBestAccuracy ? 'font-semibold text-orange-600' : ''}`}>
                        {formatMetric(task.avg_accuracy)}
                      </td>
                      <td className="px-4 py-3">{formatTokenMetric(task.avg_input_tokens)}</td>
                      <td className="px-4 py-3">{formatTokenMetric(task.avg_output_tokens)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {[isBestRecall ? '召回率最高' : '', isBestAccuracy ? '准确率最高' : '']
                          .filter(Boolean)
                          .join(' / ') || '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
