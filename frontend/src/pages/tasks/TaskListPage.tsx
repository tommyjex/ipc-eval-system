import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { taskApi, datasetApi } from '../../api';
import type { EvaluationTask, TaskStatus, Dataset } from '../../api';

export const TaskListPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<EvaluationTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [newTask, setNewTask] = useState({
    name: '',
    dataset_id: '',
    model_provider: 'volcengine',
    target_model: '',
    scoring_criteria: '',
  });
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState<50 | 100>(50);

  const modelOptions: Record<string, { label: string; models: { value: string; label: string }[] }> = {
    volcengine: {
      label: '火山引擎',
      models: [
        { value: 'doubao-seed-2-0-pro', label: 'Seed 2.0 Pro' },
        { value: 'doubao-seed-2-0-lite', label: 'Seed 2.0 Lite' },
      ],
    },
    aliyun: {
      label: '阿里千问',
      models: [
        { value: 'qwen-vl-max', label: 'Qwen-VL-Max' },
        { value: 'qwen-vl-plus', label: 'Qwen-VL-Plus' },
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
      const res = await taskApi.list({
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

  useEffect(() => {
    fetchTasks();
    fetchDatasets();
  }, [page, pageSize]);

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
      });
      setShowCreateModal(false);
      setNewTask({ name: '', dataset_id: '', model_provider: 'volcengine', target_model: '', scoring_criteria: '' });
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

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">评测任务</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          创建任务
        </button>
      </div>

      {loading ? (
        <div className="text-center py-10">加载中...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-10 text-gray-500">暂无评测任务</div>
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
                  <td className="px-4 py-3">{task.dataset_id}</td>
                  <td className="px-4 py-3">{getProviderLabel(task.model_provider)}</td>
                  <td className="px-4 py-3">{task.target_model}</td>
                  <td className="px-4 py-3">{getStatusBadge(task.status)}</td>
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
                    const provider = e.target.value;
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
                <label className="block text-sm font-medium mb-1">评分标准</label>
                <textarea
                  value={newTask.scoring_criteria}
                  onChange={(e) => setNewTask({ ...newTask, scoring_criteria: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  rows={3}
                  placeholder="可选，输入评分标准"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-4 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
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
    </div>
  );
};
