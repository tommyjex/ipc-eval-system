import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { taskApi, datasetApi, scoringTemplateApi, promptTemplateApi } from '../../api';
import type { EvaluationTask, TaskStatus, Dataset, DatasetScene, ModelProvider, ScoringTemplate, PromptTemplate } from '../../api';

const getRecentTemplateStorageKey = (scene: DatasetScene) => `recent-scoring-template:${scene}`;
const getRecentPromptTemplateStorageKey = (scene: DatasetScene) => `recent-prompt-template:${scene}`;
const normalizeFps = (value: number) => Math.max(0.01, Math.min(30, Number(value.toFixed(2))));
const formatMetric = (value: number | null) => (value == null ? '-' : `${value.toFixed(2)}%`);

export const TaskListPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<EvaluationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [newTask, setNewTask] = useState<{
    name: string;
    dataset_id: string;
    model_provider: ModelProvider;
    target_model: string;
    scoring_criteria: string;
    prompt: string;
    fps: number;
  }>({
    name: '',
    dataset_id: '',
    model_provider: 'volcengine',
    target_model: '',
    scoring_criteria: '',
    prompt: '',
    fps: 0.3,
  });
  const [creating, setCreating] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showPromptTemplateModal, setShowPromptTemplateModal] = useState(false);
  const [templates, setTemplates] = useState<ScoringTemplate[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [promptTemplateLoading, setPromptTemplateLoading] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [promptTemplateSaving, setPromptTemplateSaving] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [editingPromptTemplateId, setEditingPromptTemplateId] = useState<number | null>(null);
  const [templateForm, setTemplateForm] = useState<{
    name: string;
    scene: DatasetScene;
    description: string;
    content: string;
  }>({
    name: '',
    scene: 'video_retrieval',
    description: '',
    content: '',
  });
  const [promptTemplateForm, setPromptTemplateForm] = useState<{
    name: string;
    scene: DatasetScene;
    description: string;
    content: string;
  }>({
    name: '',
    scene: 'video_retrieval',
    description: '',
    content: '',
  });
  const [page] = useState(1);
  const [, setTotal] = useState(0);
  const [pageSize] = useState<50 | 100>(50);
  const [statusFilter, setStatusFilter] = useState<'all' | TaskStatus>('all');
  const [datasetFilter, setDatasetFilter] = useState<'all' | string>('all');
  const [sortOption, setSortOption] = useState<'default' | 'avg_recall_desc' | 'avg_recall_asc' | 'avg_accuracy_desc' | 'avg_accuracy_asc'>('default');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [selectedPromptTemplateId, setSelectedPromptTemplateId] = useState('');

  const sceneLabels: Record<DatasetScene, string> = {
    video_retrieval: '视频检索',
    smart_alert: '智能告警',
  };

  const modelOptions: Record<string, { label: string; models: { value: string; label: string }[] }> = {
    volcengine: {
      label: '火山引擎',
      models: [
        { value: 'doubao-seed-2-0-pro-260215', label: 'Seed 2.0 Pro' },
        { value: 'doubao-seed-2-0-lite-260215', label: 'Seed 2.0 Lite' },
        { value: 'doubao-seed-2-0-mini-260215', label: 'Seed 2.0 Mini' },
      ],
    },
    aliyun: {
      label: '阿里千问',
      models: [
        { value: 'qwen3.6-plus', label: 'qwen3.6-plus' },
        { value: 'qwen3.5-plus', label: 'qwen3.5-plus' },
        { value: 'qwen3.5-flash', label: 'qwen3.5-flash' },
        { value: 'qwen-flash', label: 'qwen-flash' },
        { value: 'qwen3-max', label: 'qwen3-max' },
      ],
    },
    gemini: {
      label: 'Gemini',
      models: [
        { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
        { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
      ],
    },
    openai: {
      label: 'OpenAI',
      models: [
        { value: 'gpt-4o', label: 'GPT-4o' },
        { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
      ],
    },
    aws: {
      label: 'AWS Nova',
      models: [
        { value: 'nova-pro', label: 'Nova Pro' },
        { value: 'nova-lite', label: 'Nova Lite' },
      ],
    },
  };

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const [sortBy, sortOrder] = sortOption === 'default'
        ? [undefined, undefined]
        : sortOption.split('_').slice(0, 2).join('_') === 'avg_recall'
          ? ['avg_recall', sortOption.endsWith('_asc') ? 'asc' : 'desc']
          : ['avg_accuracy', sortOption.endsWith('_asc') ? 'asc' : 'desc'];
      const res = await taskApi.list({
        dataset_id: datasetFilter === 'all' ? undefined : parseInt(datasetFilter),
        status: statusFilter === 'all' ? undefined : statusFilter,
        sort_by: sortBy as 'avg_recall' | 'avg_accuracy' | undefined,
        sort_order: sortOrder as 'asc' | 'desc' | undefined,
        page,
        page_size: pageSize,
      });
      setTasks(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('获取任务列表失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDatasets = async () => {
    try {
      const res = await datasetApi.list({ page: 1, page_size: 100 });
      setDatasets(res.items);
    } catch (err) {
      console.error('获取评测集列表失败:', err);
    }
  };

  const fetchTemplates = async () => {
    setTemplateLoading(true);
    try {
      const res = await scoringTemplateApi.list();
      setTemplates(res.items);
    } catch (err) {
      console.error('获取评分模板失败:', err);
    } finally {
      setTemplateLoading(false);
    }
  };

  const fetchPromptTemplates = async () => {
    setPromptTemplateLoading(true);
    try {
      const res = await promptTemplateApi.list();
      setPromptTemplates(res.items);
    } catch (err) {
      console.error('获取 Prompt 模板失败:', err);
    } finally {
      setPromptTemplateLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    fetchDatasets();
    fetchTemplates();
    fetchPromptTemplates();
  }, [page, pageSize, statusFilter, datasetFilter, sortOption]);

  const handleCreate = async () => {
    if (!newTask.name.trim() || !newTask.dataset_id || !newTask.target_model) return;
    setCreating(true);
    try {
      await taskApi.create({
        dataset_id: parseInt(newTask.dataset_id),
        name: newTask.name,
        target_model: newTask.target_model,
        model_provider: newTask.model_provider,
        scoring_criteria: newTask.scoring_criteria || undefined,
        prompt: newTask.prompt || undefined,
        fps: newTask.fps,
      });
      setShowCreateModal(false);
      setNewTask({ name: '', dataset_id: '', model_provider: 'volcengine', target_model: '', scoring_criteria: '', prompt: '', fps: 0.3 });
      setSelectedTemplateId('');
      setSelectedPromptTemplateId('');
      fetchTasks();
    } catch (err) {
      alert('创建失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (taskId: number) => {
    try {
      await taskApi.run(taskId);
      fetchTasks();
    } catch (err) {
      alert('启动失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleDelete = async (taskId: number) => {
    if (!confirm('确定要删除这个任务吗？')) return;
    try {
      await taskApi.delete(taskId);
      fetchTasks();
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const resetTemplateForm = () => {
    setEditingTemplateId(null);
    setTemplateForm({
      name: '',
      scene: 'video_retrieval',
      description: '',
      content: '',
    });
  };

  const resetPromptTemplateForm = () => {
    setEditingPromptTemplateId(null);
    setPromptTemplateForm({
      name: '',
      scene: 'video_retrieval',
      description: '',
      content: '',
    });
  };

  const handleSaveTemplate = async () => {
    if (!templateForm.name.trim() || !templateForm.content.trim()) return;
    setTemplateSaving(true);
    try {
      const payload = {
        name: templateForm.name.trim(),
        scene: templateForm.scene,
        description: templateForm.description.trim() || undefined,
        content: templateForm.content.trim(),
      };
      if (editingTemplateId) {
        await scoringTemplateApi.update(editingTemplateId, payload);
      } else {
        await scoringTemplateApi.create(payload);
      }
      await fetchTemplates();
      resetTemplateForm();
    } catch (err) {
      alert('保存模板失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleEditTemplate = (template: ScoringTemplate) => {
    setEditingTemplateId(template.id);
    setTemplateForm({
      name: template.name,
      scene: template.scene,
      description: template.description || '',
      content: template.content,
    });
  };

  const handleSavePromptTemplate = async () => {
    if (!promptTemplateForm.name.trim() || !promptTemplateForm.content.trim()) return;
    setPromptTemplateSaving(true);
    try {
      const payload = {
        name: promptTemplateForm.name.trim(),
        scene: promptTemplateForm.scene,
        description: promptTemplateForm.description.trim() || undefined,
        content: promptTemplateForm.content.trim(),
      };
      if (editingPromptTemplateId) {
        await promptTemplateApi.update(editingPromptTemplateId, payload);
      } else {
        await promptTemplateApi.create(payload);
      }
      await fetchPromptTemplates();
      resetPromptTemplateForm();
    } catch (err) {
      alert('保存 Prompt 模板失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setPromptTemplateSaving(false);
    }
  };

  const handleEditPromptTemplate = (template: PromptTemplate) => {
    setEditingPromptTemplateId(template.id);
    setPromptTemplateForm({
      name: template.name,
      scene: template.scene,
      description: template.description || '',
      content: template.content,
    });
  };

  const handleDeleteTemplate = async (templateId: number) => {
    if (!confirm('确定要删除这个评分模板吗？')) return;
    try {
      await scoringTemplateApi.delete(templateId);
      await fetchTemplates();
      if (editingTemplateId === templateId) {
        resetTemplateForm();
      }
    } catch (err) {
      alert('删除模板失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleDeletePromptTemplate = async (templateId: number) => {
    if (!confirm('确定要删除这个 Prompt 模板吗？')) return;
    try {
      await promptTemplateApi.delete(templateId);
      await fetchPromptTemplates();
      if (editingPromptTemplateId === templateId) {
        resetPromptTemplateForm();
      }
    } catch (err) {
      alert('删除 Prompt 模板失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const selectedDataset = datasets.find((item) => String(item.id) === newTask.dataset_id);
  const selectedScene = selectedDataset?.scene || null;
  const availableTemplates = selectedScene
    ? templates.filter((template) => template.scene === selectedScene)
    : [];
  const availablePromptTemplates = selectedScene
    ? promptTemplates.filter((template) => template.scene === selectedScene)
    : [];

  useEffect(() => {
    if (!showCreateModal) return;
    if (!selectedScene) {
      setSelectedTemplateId('');
      setSelectedPromptTemplateId('');
      return;
    }

    const recentTemplateId = window.localStorage.getItem(getRecentTemplateStorageKey(selectedScene));
    const recentTemplate = availableTemplates.find((template) => String(template.id) === recentTemplateId);
    if (!recentTemplate) {
      setSelectedTemplateId('');
    } else {
      setSelectedTemplateId(String(recentTemplate.id));
      if (!newTask.scoring_criteria.trim()) {
        setNewTask((prev) => ({ ...prev, scoring_criteria: recentTemplate.content }));
      }
    }

    const recentPromptTemplateId = window.localStorage.getItem(getRecentPromptTemplateStorageKey(selectedScene));
    const recentPromptTemplate = availablePromptTemplates.find((template) => String(template.id) === recentPromptTemplateId);
    if (!recentPromptTemplate) {
      setSelectedPromptTemplateId('');
      return;
    }

    setSelectedPromptTemplateId(String(recentPromptTemplate.id));
    if (!newTask.prompt.trim()) {
      setNewTask((prev) => ({ ...prev, prompt: recentPromptTemplate.content }));
    }
  }, [showCreateModal, selectedScene, availableTemplates, availablePromptTemplates]);

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

  const getProviderLabel = (provider: string | null) => {
    if (!provider) return '-';
    const labels: Record<string, string> = {
      volcengine: '火山引擎',
      aliyun: '阿里千问',
      gemini: 'Gemini',
      openai: 'OpenAI',
      aws: 'AWS Nova',
    };
    return labels[provider] || provider;
  };

  const getDatasetLabel = (datasetId: number) => {
    const dataset = datasets.find((item) => item.id === datasetId);
    return dataset ? dataset.name : String(datasetId);
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">评测任务</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="task-dataset-filter" className="text-sm text-gray-600">
              评测集
            </label>
            <select
              id="task-dataset-filter"
              value={datasetFilter}
              onChange={(e) => setDatasetFilter(e.target.value)}
              className="rounded border px-3 py-2 text-sm"
            >
              <option value="all">全部</option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="task-status-filter" className="text-sm text-gray-600">
              任务状态
            </label>
            <select
              id="task-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | TaskStatus)}
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
            <label htmlFor="task-sort-option" className="text-sm text-gray-600">
              排序方式
            </label>
            <select
              id="task-sort-option"
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value as typeof sortOption)}
              className="rounded border px-3 py-2 text-sm"
            >
              <option value="default">默认</option>
              <option value="avg_recall_desc">召回率降序</option>
              <option value="avg_recall_asc">召回率升序</option>
              <option value="avg_accuracy_desc">准确率降序</option>
              <option value="avg_accuracy_asc">准确率升序</option>
            </select>
          </div>
          <button
            onClick={() => setShowTemplateModal(true)}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            评分模板管理
          </button>
          <button
            onClick={() => setShowPromptTemplateModal(true)}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            Prompt模板管理
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            创建任务
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10">加载中...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-10 text-gray-500">
          {statusFilter === 'all' ? '暂无评测任务' : '当前筛选条件下暂无评测任务'}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">任务名称</th>
                <th className="px-4 py-3 text-left">评测集</th>
                <th className="px-4 py-3 text-left">模型供应商</th>
                <th className="px-4 py-3 text-left">目标模型</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">平均召回率</th>
                <th className="px-4 py-3 text-left">平均准确率</th>
                <th className="px-4 py-3 text-left">创建时间</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span
                      onClick={() => navigate(`/tasks/${task.id}`)}
                      className="text-blue-600 hover:text-blue-800 cursor-pointer hover:underline"
                    >
                      {task.name}
                    </span>
                  </td>
                  <td className="px-4 py-3">{getDatasetLabel(task.dataset_id)}</td>
                  <td className="px-4 py-3">{getProviderLabel(task.model_provider)}</td>
                  <td className="px-4 py-3">{task.target_model}</td>
                  <td className="px-4 py-3">{getStatusBadge(task.status)}</td>
                  <td className="px-4 py-3">{formatMetric(task.avg_recall)}</td>
                  <td className="px-4 py-3">{formatMetric(task.avg_accuracy)}</td>
                  <td className="px-4 py-3">
                    {new Date(task.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex space-x-2">
                      <button
                        onClick={() => navigate(`/tasks/${task.id}`)}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        查看
                      </button>
                      {task.status === 'pending' && (
                        <button
                          onClick={() => handleRun(task.id)}
                          className="text-green-600 hover:text-green-800"
                        >
                          运行
                        </button>
                      )}
                      {task.status === 'failed' && (
                        <button
                          onClick={() => handleRun(task.id)}
                          className="text-green-600 hover:text-green-800"
                        >
                          重新运行
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(task.id)}
                        className="text-red-600 hover:text-red-800"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">创建评测任务</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">任务名称</label>
                <input
                  type="text"
                  value={newTask.name}
                  onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="请输入任务名称"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">评测集</label>
                <select
                  value={newTask.dataset_id}
                  onChange={(e) => setNewTask({ ...newTask, dataset_id: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="">请选择评测集</option>
                  {datasets.map((ds) => (
                    <option key={ds.id} value={ds.id}>
                      {ds.name} ({ds.data_count}条数据)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">模型供应商</label>
                <select
                  value={newTask.model_provider}
                  onChange={(e) => {
                    const provider = e.target.value as ModelProvider;
                    const firstModel = modelOptions[provider]?.models[0]?.value || '';
                    setNewTask({ ...newTask, model_provider: provider, target_model: firstModel });
                  }}
                  className="w-full px-3 py-2 border rounded"
                >
                  {Object.entries(modelOptions).map(([key, { label }]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">目标模型</label>
                <select
                  value={newTask.target_model}
                  onChange={(e) => setNewTask({ ...newTask, target_model: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="">请选择模型</option>
                  {modelOptions[newTask.model_provider]?.models.map((model) => (
                    <option key={model.value} value={model.value}>{model.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">视频帧率 (fps)</label>
                <input
                  type="number"
                  min={0.01}
                  max={30}
                  step={0.01}
                  value={newTask.fps}
                  onChange={(e) => setNewTask({ ...newTask, fps: normalizeFps(Number(e.target.value) || 0.3) })}
                  className="w-full px-3 py-2 border rounded"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">评分标准</label>
                {selectedScene ? (
                  <div className="mb-2 flex items-center gap-2">
                    <select
                      value={selectedTemplateId}
                      onChange={(e) => {
                        setSelectedTemplateId(e.target.value);
                        const template = availableTemplates.find((item) => String(item.id) === e.target.value);
                        if (template) {
                          window.localStorage.setItem(getRecentTemplateStorageKey(selectedScene), String(template.id));
                          setNewTask({ ...newTask, scoring_criteria: template.content });
                        }
                      }}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">选择{sceneLabels[selectedScene]}模板</option>
                      {availableTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => setShowTemplateModal(true)}
                      className="shrink-0 rounded border px-3 py-2 text-sm hover:bg-gray-50"
                    >
                      管理模板
                    </button>
                  </div>
                ) : (
                  <p className="mb-2 text-xs text-gray-500">请先选择带业务场景的评测集，再选择评分模板。</p>
                )}
                <textarea
                  value={newTask.scoring_criteria}
                  onChange={(e) => setNewTask({ ...newTask, scoring_criteria: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  rows={3}
                  placeholder="可选，输入评分标准"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Prompt</label>
                {selectedScene ? (
                  <div className="mb-2 flex items-center gap-2">
                    <select
                      value={selectedPromptTemplateId}
                      onChange={(e) => {
                        setSelectedPromptTemplateId(e.target.value);
                        const template = availablePromptTemplates.find((item) => String(item.id) === e.target.value);
                        if (template) {
                          window.localStorage.setItem(getRecentPromptTemplateStorageKey(selectedScene), String(template.id));
                          setNewTask({ ...newTask, prompt: template.content });
                        }
                      }}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">选择{sceneLabels[selectedScene]}Prompt模板</option>
                      {availablePromptTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => setShowPromptTemplateModal(true)}
                      className="shrink-0 rounded border px-3 py-2 text-sm hover:bg-gray-50"
                    >
                      管理模板
                    </button>
                  </div>
                ) : (
                  <p className="mb-2 text-xs text-gray-500">请先选择带业务场景的评测集，再选择 Prompt 模板。</p>
                )}
                <textarea
                  value={newTask.prompt}
                  onChange={(e) => setNewTask({ ...newTask, prompt: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  rows={4}
                  placeholder="可选，输入任务级 Prompt"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-4 mt-6">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setSelectedTemplateId('');
                  setSelectedPromptTemplateId('');
                }}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newTask.name.trim() || !newTask.dataset_id || !newTask.target_model}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">评分标准模板管理</h2>
              <button
                onClick={() => {
                  setShowTemplateModal(false);
                  resetTemplateForm();
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <div className="mb-6 grid gap-4 rounded border p-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">模板名称</label>
                <input
                  type="text"
                  value={templateForm.name}
                  onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  placeholder="请输入模板名称"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">业务场景</label>
                <select
                  value={templateForm.scene}
                  onChange={(e) => setTemplateForm({ ...templateForm, scene: e.target.value as DatasetScene })}
                  className="w-full rounded border px-3 py-2"
                >
                  <option value="video_retrieval">视频检索</option>
                  <option value="smart_alert">智能告警</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-sm font-medium">模板描述</label>
                <input
                  type="text"
                  value={templateForm.description}
                  onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  placeholder="可选，输入模板描述"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-sm font-medium">评分标准内容</label>
                <textarea
                  value={templateForm.content}
                  onChange={(e) => setTemplateForm({ ...templateForm, content: e.target.value })}
                  rows={6}
                  className="w-full rounded border px-3 py-2"
                  placeholder="请输入评分标准模板内容"
                />
              </div>
              <div className="md:col-span-2 flex justify-end gap-3">
                {editingTemplateId && (
                  <button
                    type="button"
                    onClick={resetTemplateForm}
                    className="rounded border px-4 py-2 hover:bg-gray-50"
                  >
                    取消编辑
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleSaveTemplate}
                  disabled={templateSaving || !templateForm.name.trim() || !templateForm.content.trim()}
                  className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:bg-gray-400"
                >
                  {templateSaving ? '保存中...' : (editingTemplateId ? '保存模板' : '创建模板')}
                </button>
              </div>
            </div>

            {templateLoading ? (
              <div className="py-10 text-center text-gray-500">模板加载中...</div>
            ) : templates.length === 0 ? (
              <div className="py-10 text-center text-gray-500">暂无评分标准模板</div>
            ) : (
              <div className="overflow-hidden rounded border">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left">模板名称</th>
                      <th className="px-4 py-3 text-left">业务场景</th>
                      <th className="px-4 py-3 text-left">模板描述</th>
                      <th className="px-4 py-3 text-left">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((template) => (
                      <tr key={template.id} className="border-t">
                        <td className="px-4 py-3">{template.name}</td>
                        <td className="px-4 py-3">{sceneLabels[template.scene]}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{template.description || '-'}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-3">
                            <button
                              type="button"
                              onClick={() => handleEditTemplate(template)}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteTemplate(template.id)}
                              className="text-red-600 hover:text-red-800"
                            >
                              删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {showPromptTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-lg bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">Prompt 模板管理</h2>
              <button
                onClick={() => {
                  setShowPromptTemplateModal(false);
                  resetPromptTemplateForm();
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <div className="mb-6 grid gap-4 rounded border p-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">模板名称</label>
                <input
                  type="text"
                  value={promptTemplateForm.name}
                  onChange={(e) => setPromptTemplateForm({ ...promptTemplateForm, name: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  placeholder="请输入 Prompt 模板名称"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">业务场景</label>
                <select
                  value={promptTemplateForm.scene}
                  onChange={(e) => setPromptTemplateForm({ ...promptTemplateForm, scene: e.target.value as DatasetScene })}
                  className="w-full rounded border px-3 py-2"
                >
                  <option value="video_retrieval">视频检索</option>
                  <option value="smart_alert">智能告警</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-sm font-medium">模板描述</label>
                <input
                  type="text"
                  value={promptTemplateForm.description}
                  onChange={(e) => setPromptTemplateForm({ ...promptTemplateForm, description: e.target.value })}
                  className="w-full rounded border px-3 py-2"
                  placeholder="可选，输入 Prompt 模板描述"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-sm font-medium">Prompt 内容</label>
                <textarea
                  value={promptTemplateForm.content}
                  onChange={(e) => setPromptTemplateForm({ ...promptTemplateForm, content: e.target.value })}
                  rows={6}
                  className="w-full rounded border px-3 py-2"
                  placeholder="请输入 Prompt 模板内容"
                />
              </div>
              <div className="md:col-span-2 flex justify-end gap-3">
                {editingPromptTemplateId && (
                  <button
                    type="button"
                    onClick={resetPromptTemplateForm}
                    className="rounded border px-4 py-2 hover:bg-gray-50"
                  >
                    取消编辑
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleSavePromptTemplate}
                  disabled={promptTemplateSaving || !promptTemplateForm.name.trim() || !promptTemplateForm.content.trim()}
                  className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:bg-gray-400"
                >
                  {promptTemplateSaving ? '保存中...' : (editingPromptTemplateId ? '保存模板' : '创建模板')}
                </button>
              </div>
            </div>

            {promptTemplateLoading ? (
              <div className="py-10 text-center text-gray-500">模板加载中...</div>
            ) : promptTemplates.length === 0 ? (
              <div className="py-10 text-center text-gray-500">暂无 Prompt 模板</div>
            ) : (
              <div className="overflow-hidden rounded border">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left">模板名称</th>
                      <th className="px-4 py-3 text-left">业务场景</th>
                      <th className="px-4 py-3 text-left">模板描述</th>
                      <th className="px-4 py-3 text-left">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {promptTemplates.map((template) => (
                      <tr key={template.id} className="border-t">
                        <td className="px-4 py-3">{template.name}</td>
                        <td className="px-4 py-3">{sceneLabels[template.scene]}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{template.description || '-'}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-3">
                            <button
                              type="button"
                              onClick={() => handleEditPromptTemplate(template)}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeletePromptTemplate(template.id)}
                              className="text-red-600 hover:text-red-800"
                            >
                              删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
