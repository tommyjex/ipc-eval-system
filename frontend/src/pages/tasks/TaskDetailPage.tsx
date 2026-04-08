import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { taskApi } from '../../api';
import type { EvaluationTask, TaskResultDetail, TaskStatus } from '../../api';

export const TaskDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<EvaluationTask | null>(null);
  const [results, setResults] = useState<TaskResultDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState<50 | 100>(50);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<TaskResultDetail | null>(null);

  const fetchTask = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const taskRes = await taskApi.get(parseInt(id));
      setTask(taskRes);
      
      const resultsRes = await taskApi.getResultsDetail(parseInt(id), { page, page_size: pageSize });
      setResults(resultsRes);
      setTotal(resultsRes.length);
    } catch (err) {
      console.error('获取任务详情失败:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTask();
  }, [id, page, pageSize]);

  const handleRun = async () => {
    if (!id) return;
    try {
      await taskApi.run(parseInt(id));
      fetchTask();
    } catch (err) {
      alert('启动失败: ' + (err instanceof Error ? err.message : '未知错误'));
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

  const isVideo = (fileType: string) => 
    ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'].includes(fileType.toLowerCase());

  if (loading) {
    return <div className="p-6 text-center">加载中...</div>;
  }

  if (!task) {
    return <div className="p-6 text-center text-gray-500">任务不存在</div>;
  }

  return (
    <div className="p-6">
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-2xl font-bold mb-2">{task.name}</h1>
            <div className="flex items-center space-x-4 text-sm">
              <span className="text-gray-600">目标模型: {task.target_model}</span>
              {getStatusBadge(task.status)}
            </div>
          </div>
          <div className="flex space-x-2">
            {task.status === 'pending' && (
              <button
                onClick={handleRun}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                运行任务
              </button>
            )}
            <button
              onClick={handleDelete}
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              删除任务
            </button>
          </div>
        </div>
        
        {task.scoring_criteria && (
          <div className="mt-4 pt-4 border-t">
            <h3 className="text-sm font-medium text-gray-700 mb-2">评分标准</h3>
            <p className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded">
              {task.scoring_criteria}
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

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-bold">评测结果 ({total}条)</h2>
        </div>
        
        {results.length === 0 ? (
          <div className="p-10 text-center text-gray-500">
            {task.status === 'pending' ? '请运行任务查看评测结果' : '暂无评测结果'}
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
                  <th className="px-4 py-3 text-left">评测时间</th>
                  <th className="px-4 py-3 text-left">智能评分</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr key={result.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3">{result.file_name}</td>
                    <td className="px-4 py-3">
                      {result.download_url && (
                        <div 
                          className="w-16 h-16 cursor-pointer"
                          onClick={() => openPreview(result)}
                        >
                          {isVideo(result.file_type) ? (
                            <video 
                              src={result.download_url} 
                              className="w-full h-full object-cover rounded"
                              muted
                            />
                          ) : (
                            <img 
                              src={result.download_url} 
                              alt={result.file_name}
                              className="w-full h-full object-cover rounded"
                            />
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600 max-w-xs truncate">
                        {result.ground_truth || '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-600 max-w-xs truncate">
                        {result.model_output || '-'}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {new Date(result.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td className="px-4 py-3">
                      {result.score !== null ? (
                        <span className={`px-2 py-1 rounded text-xs ${
                          result.score >= 80 ? 'bg-green-100 text-green-800' :
                          result.score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {result.score}分
                        </span>
                      ) : '-'}
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
            </div>
          </>
        )}
      </div>

      {showPreview && previewData && previewData.download_url && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-lg shadow-lg max-w-4xl max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">{previewData.file_name}</h3>
              <button onClick={() => setShowPreview(false)} className="text-gray-500 hover:text-gray-700">✕</button>
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
