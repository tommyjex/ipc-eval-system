import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { datasetApi } from '../../api';
import type { Dataset, DatasetType, DatasetAnnotationStatus } from '../../api';

export const DatasetListPage: React.FC = () => {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    type: '' as DatasetType | '',
    annotation_status: '' as DatasetAnnotationStatus | '',
    keyword: '',
  });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState<50 | 100>(50);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const res = await datasetApi.list({
        type: filters.type || undefined,
        annotation_status: filters.annotation_status || undefined,
        keyword: filters.keyword || undefined,
        page,
        page_size: pageSize,
      });
      setDatasets(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('获取评测集列表失败:', err);
      alert('获取评测集列表失败，请检查网络连接或使用外部浏览器访问');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, [page, filters.type, filters.annotation_status, pageSize]);

  const getAnnotationStatusBadge = (status: DatasetAnnotationStatus) => {
    const styles: Record<DatasetAnnotationStatus, string> = {
      pending: 'bg-gray-100 text-gray-800',
      partial: 'bg-yellow-100 text-yellow-800',
      annotated: 'bg-green-100 text-green-800',
    };
    const labels: Record<DatasetAnnotationStatus, string> = {
      pending: '待标注',
      partial: '部分标注',
      annotated: '已标注',
    };
    return <span className={`px-2 py-1 rounded text-xs ${styles[status]}`}>{labels[status]}</span>;
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这个评测集吗？')) return;
    try {
      await datasetApi.delete(id);
      fetchDatasets();
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handlePageSizeChange = (newSize: 50 | 100) => {
    setPageSize(newSize);
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">评测集管理</h1>
        <button
          onClick={() => navigate('/datasets/create')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          创建评测集
        </button>
      </div>

      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex space-x-4">
          <input
            type="text"
            placeholder="搜索评测集名称..."
            value={filters.keyword}
            onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
            className="flex-1 px-3 py-2 border rounded"
          />
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value as DatasetType | '' })}
            className="px-3 py-2 border rounded"
          >
            <option value="">全部类型</option>
            <option value="image">图片</option>
            <option value="video">视频</option>
            <option value="mixed">图片+视频</option>
          </select>
          <select
            value={filters.annotation_status}
            onChange={(e) => setFilters({ ...filters, annotation_status: e.target.value as DatasetAnnotationStatus | '' })}
            className="px-3 py-2 border rounded"
          >
            <option value="">全部状态</option>
            <option value="pending">待标注</option>
            <option value="partial">部分标注</option>
            <option value="annotated">已标注</option>
          </select>
          <button
            onClick={fetchDatasets}
            className="px-4 py-2 bg-gray-100 rounded hover:bg-gray-200"
          >
            搜索
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10">加载中...</div>
      ) : datasets.length === 0 ? (
        <div className="text-center py-10 text-gray-500">暂无评测集</div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">名称</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">业务场景</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">数据量</th>
                <th className="px-4 py-3 text-left">已标注</th>
                <th className="px-4 py-3 text-left">创建时间</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((dataset) => (
                <tr key={dataset.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span
                      onClick={() => navigate(`/datasets/${dataset.id}`)}
                      className="text-blue-600 hover:text-blue-800 cursor-pointer hover:underline"
                    >
                      {dataset.name}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      dataset.type === 'video' ? 'bg-purple-100 text-purple-800' : 
                      dataset.type === 'image' ? 'bg-green-100 text-green-800' : 
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {dataset.type === 'video' ? '视频' : dataset.type === 'image' ? '图片' : '图片+视频'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {dataset.scene && (
                      <span className={`px-2 py-1 rounded text-xs ${
                        dataset.scene === 'video_retrieval' ? 'bg-orange-100 text-orange-800' : 
                        'bg-teal-100 text-teal-800'
                      }`}>
                        {dataset.scene === 'video_retrieval' ? '录像检索' : '智能消息告警'}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {getAnnotationStatusBadge(dataset.annotation_status)}
                  </td>
                  <td className="px-4 py-3">{dataset.data_count}</td>
                  <td className="px-4 py-3">{dataset.annotated_count}</td>
                  <td className="px-4 py-3">
                    {new Date(dataset.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex space-x-2">
                      <button
                        onClick={() => navigate(`/datasets/${dataset.id}`)}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        查看
                      </button>
                      <button
                        onClick={() => handleDelete(dataset.id)}
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

      {total > 0 && (
        <div className="flex justify-between items-center mt-6">
          <div className="flex items-center space-x-2">
            <span className="text-gray-500">共 {total} 条</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value) as 50 | 100); setPage(1); }}
              className="px-2 py-1 border rounded"
            >
              <option value={50}>50条/页</option>
              <option value={100}>100条/页</option>
            </select>
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              上一页
            </button>
            <span className="px-3 py-1">
              第 {page} / {totalPages} 页
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
