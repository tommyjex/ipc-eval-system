import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { datasetApi } from '../../api';
import type { DatasetType, DatasetScene } from '../../api';

export const DatasetCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    description: '',
    type: 'image' as DatasetType,
    scene: '' as DatasetScene | '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [debugInfo, setDebugInfo] = useState<string>('');

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!form.name.trim()) {
      newErrors.name = '评测集名称不能为空';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setDebugInfo('开始提交...');
    
    if (!validate()) {
      setDebugInfo('验证失败');
      return;
    }

    setSubmitting(true);
    setDebugInfo('正在创建评测集...');
    
    try {
      const submitData = {
        name: form.name,
        description: form.description || undefined,
        type: form.type,
        scene: form.scene || undefined,
      };
      const dataset = await datasetApi.create(submitData);
      setDebugInfo(`创建成功，ID: ${dataset.id}`);
      navigate(`/datasets/${dataset.id}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '未知错误';
      setDebugInfo(`创建失败: ${errorMsg}`);
      alert('创建失败: ' + errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">创建评测集</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">
            评测集名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={`w-full px-3 py-2 border rounded ${errors.name ? 'border-red-500' : ''}`}
            placeholder="请输入评测集名称"
          />
          {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">评测集类型</label>
          <div className="flex flex-col space-y-2">
            <label className="flex items-center">
              <input
                type="radio"
                name="type"
                value="image"
                checked={form.type === 'image'}
                onChange={() => setForm({ ...form, type: 'image' })}
                className="mr-2"
              />
              图片
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="type"
                value="video"
                checked={form.type === 'video'}
                onChange={() => setForm({ ...form, type: 'video' })}
                className="mr-2"
              />
              视频
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="type"
                value="mixed"
                checked={form.type === 'mixed'}
                onChange={() => setForm({ ...form, type: 'mixed' })}
                className="mr-2"
              />
              图片+视频
            </label>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">业务场景</label>
          <select
            value={form.scene}
            onChange={(e) => setForm({ ...form, scene: e.target.value as DatasetScene | '' })}
            className="w-full px-3 py-2 border rounded"
          >
            <option value="">请选择业务场景</option>
            <option value="video_retrieval">录像检索</option>
            <option value="smart_alert">智能消息告警</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">描述</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 border rounded"
            rows={4}
            placeholder="请输入评测集描述"
          />
        </div>

        {debugInfo && (
          <div className="text-sm text-gray-600 bg-gray-100 p-2 rounded">
            {debugInfo}
          </div>
        )}

        <div className="flex justify-end space-x-4">
          <button
            type="button"
            onClick={() => navigate('/datasets')}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
          >
            {submitting ? '创建中...' : '创建'}
          </button>
        </div>
      </form>
    </div>
  );
};
