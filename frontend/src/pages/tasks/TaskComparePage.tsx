import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { datasetApi, taskApi } from '../../api';
import type { Dataset, EvaluationTask } from '../../api';

const formatMetric = (value: number | null) => (value == null ? '-' : `${value.toFixed(2)}%`);
const getBarWidth = (value: number | null) => `${Math.max(0, Math.min(100, value ?? 0))}%`;
type MultiSelectOption = { value: string; label: string };

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
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">指标柱状图</h2>
                <p className="mt-1 text-sm text-gray-600">绿色表示召回率，橙色表示准确率，颜色更深表示该维度最优。</p>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-600">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded bg-green-400" />
                  <span>召回率</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded bg-orange-400" />
                  <span>准确率</span>
                </div>
              </div>
            </div>
            <div className="space-y-4">
              {groupedTasks.map((task) => {
                const isBestRecall = task.avg_recall != null && task.avg_recall === bestRecall;
                const isBestAccuracy = task.avg_accuracy != null && task.avg_accuracy === bestAccuracy;
                return (
                  <div key={task.id} className="rounded border border-gray-100 p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <Link to={`/tasks/${task.id}`} className="font-medium text-blue-600 hover:text-blue-800 hover:underline">
                        {task.name}
                      </Link>
                      <div className="text-sm text-gray-500">
                        {task.model_provider} / {task.target_model}
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className={isBestRecall ? 'font-semibold text-green-700' : 'text-gray-700'}>召回率</span>
                          <span className={isBestRecall ? 'font-semibold text-green-700' : 'text-gray-700'}>
                            {formatMetric(task.avg_recall)}
                          </span>
                        </div>
                        <div className="h-4 w-full rounded-full bg-gray-100">
                          <div
                            className={`h-4 rounded-full ${isBestRecall ? 'bg-green-600' : 'bg-green-400'}`}
                            style={{ width: getBarWidth(task.avg_recall) }}
                          />
                        </div>
                      </div>
                      <div>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className={isBestAccuracy ? 'font-semibold text-orange-600' : 'text-gray-700'}>准确率</span>
                          <span className={isBestAccuracy ? 'font-semibold text-orange-600' : 'text-gray-700'}>
                            {formatMetric(task.avg_accuracy)}
                          </span>
                        </div>
                        <div className="h-4 w-full rounded-full bg-gray-100">
                          <div
                            className={`h-4 rounded-full ${isBestAccuracy ? 'bg-orange-600' : 'bg-orange-400'}`}
                            style={{ width: getBarWidth(task.avg_accuracy) }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg bg-white shadow overflow-x-auto">
            <table className="min-w-[1000px] w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left">任务名称</th>
                  <th className="px-4 py-3 text-left">模型供应商</th>
                  <th className="px-4 py-3 text-left">目标模型</th>
                  <th className="px-4 py-3 text-left">平均召回率</th>
                  <th className="px-4 py-3 text-left">平均准确率</th>
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
