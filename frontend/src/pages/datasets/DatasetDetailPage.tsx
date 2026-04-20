import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { datasetApi, evaluationDataApi, annotationApi, buildEvaluationDataPreviewUrl } from '../../api';
import type { Dataset, EvaluationData, DatasetType, DatasetScene, TOSFolder, TOSFile } from '../../api';
import { FileUpload } from '../../components/upload/FileUpload';

export const DatasetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [dataList, setDataList] = useState<EvaluationData[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [showTOSModal, setShowTOSModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewData, setPreviewData] = useState<EvaluationData | null>(null);
  const [gifPreviewUrl, setGifPreviewUrl] = useState<string | null>(null);
  const [gifPreviewLoading, setGifPreviewLoading] = useState(false);
  const [tosPath, setTosPath] = useState<string[]>([]);
  const [tosFolders, setTosFolders] = useState<TOSFolder[]>([]);
  const [tosFiles, setTosFiles] = useState<TOSFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [tosLoading, setTosLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  
  const [editingAnnotation, setEditingAnnotation] = useState<number | null>(null);
  const [annotationText, setAnnotationText] = useState('');
  const [saving, setSaving] = useState(false);
  
  const [aiAnnotatingIds, setAiAnnotatingIds] = useState<Set<number>>(new Set());
  
  const [editingBasics, setEditingBasics] = useState(false);
  const [sceneValue, setSceneValue] = useState<DatasetScene | ''>('');
  const [typeValue, setTypeValue] = useState<DatasetType>('video');
  const [nameValue, setNameValue] = useState('');
  const [savingBasics, setSavingBasics] = useState(false);
  
  const [editingPrompt, setEditingPrompt] = useState(false);
  const [promptValue, setPromptValue] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);
  
  const [editingTags, setEditingTags] = useState(false);
  const [tagsValue, setTagsValue] = useState<string>('');
  const [savingTags, setSavingTags] = useState(false);
  
  const [expandedPrompt, setExpandedPrompt] = useState(false);
  
  const [dataPage, setDataPage] = useState(1);
  const [dataTotal, setDataTotal] = useState(0);
  const [dataPageSize, setDataPageSize] = useState<50 | 100>(50);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'annotated' | 'failed'>('all');
  const [keywordInput, setKeywordInput] = useState('');
  const [keywordFilter, setKeywordFilter] = useState('');

  const fetchDataset = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const datasetRes = await datasetApi.get(parseInt(id));
      setDataset(datasetRes);
      const dataRes = await evaluationDataApi.list(parseInt(id), {
        status: statusFilter === 'all' ? undefined : statusFilter,
        keyword: keywordFilter || undefined,
        page: dataPage,
        page_size: dataPageSize
      });
      setDataList(dataRes.items);
      setDataTotal(dataRes.total);
    } catch (err) {
      console.error('获取评测集详情失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const updateDataRow = (updatedData: EvaluationData) => {
    setDataList((prev) => prev.map((item) => (item.id === updatedData.id ? updatedData : item)));
    setPreviewData((prev) => (prev && prev.id === updatedData.id ? updatedData : prev));
  };

  const fetchSingleData = async (dataId: number) => {
    if (!id) return;
    try {
      const dataRes = await evaluationDataApi.list(parseInt(id), { page: dataPage, page_size: dataPageSize });
      const freshData = dataRes.items.find((item) => item.id === dataId);
      if (freshData) {
        updateDataRow(freshData);
      }
    } catch (err) {
      console.error('刷新单条数据失败:', err);
    }
  };

  const removeRowIfFiltered = (dataId: number) => {
    if (statusFilter !== 'pending') return false;
    // In pending-only mode, once a row becomes annotated it should disappear.
    setDataList((prev) => prev.filter((item) => item.id !== dataId));
    setDataTotal((prev) => Math.max(0, prev - 1));
    return true;
  };

  useEffect(() => {
    fetchDataset();
  }, [id, dataPage, dataPageSize, statusFilter, keywordFilter]);

  useEffect(() => {
    return () => {
      if (gifPreviewUrl) {
        URL.revokeObjectURL(gifPreviewUrl);
      }
    };
  }, [gifPreviewUrl]);

  const fetchTOSFolders = async (prefix: string = '') => {
    if (!id) return;
    setTosLoading(true);
    try {
      const res = await evaluationDataApi.getTOSFolders(parseInt(id), prefix);
      setTosFolders(res.folders);
      setTosFiles([]);
      setSelectedFiles(new Set());
    } catch (err) {
      console.error('获取TOS文件夹失败:', err);
      alert('获取TOS文件夹失败');
    } finally {
      setTosLoading(false);
    }
  };

  const fetchTOSFiles = async (prefix: string) => {
    if (!id) return;
    setTosLoading(true);
    try {
      const res = await evaluationDataApi.getTOSFiles(parseInt(id), prefix);
      setTosFiles(res.files);
      setTosFolders([]);
      setSelectedFiles(new Set());
    } catch (err) {
      console.error('获取TOS文件失败:', err);
      alert('获取TOS文件失败');
    } finally {
      setTosLoading(false);
    }
  };

  const openTOSModal = () => {
    setShowTOSModal(true);
    setTosPath([]);
    fetchTOSFolders('');
  };

  const navigateToFolder = (folder: TOSFolder) => {
    const newPath = [...tosPath, folder.name];
    setTosPath(newPath);
    fetchTOSFolders(folder.prefix);
  };

  const goBack = () => {
    if (tosPath.length === 0) return;
    const newPath = tosPath.slice(0, -1);
    setTosPath(newPath);
    const prefix = newPath.join('/');
    fetchTOSFolders(prefix);
  };

  const selectFolderAndLoadFiles = (folder: TOSFolder) => {
    const newPath = [...tosPath, folder.name];
    setTosPath(newPath);
    fetchTOSFiles(folder.prefix);
  };

  const toggleFileSelection = (key: string) => {
    const newSelection = new Set(selectedFiles);
    if (newSelection.has(key)) {
      newSelection.delete(key);
    } else {
      newSelection.add(key);
    }
    setSelectedFiles(newSelection);
  };

  const selectAllFiles = () => {
    if (selectedFiles.size === tosFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(tosFiles.map(f => f.key)));
    }
  };

  const handleImport = async () => {
    if (!id || selectedFiles.size === 0) return;
    setImporting(true);
    try {
      await evaluationDataApi.importFromTOS(parseInt(id), Array.from(selectedFiles));
      setShowTOSModal(false);
      fetchDataset();
    } catch (err) {
      alert('导入失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setImporting(false);
    }
  };

  const getMediaPreviewUrl = (data: Pick<EvaluationData, 'id' | 'download_url'>) =>
    data.id ? buildEvaluationDataPreviewUrl(data.id) : (data.download_url || '');

  const openPreview = async (data: EvaluationData) => {
    setPreviewData(data);
    setShowPreviewModal(true);

    if (gifPreviewUrl) {
      URL.revokeObjectURL(gifPreviewUrl);
      setGifPreviewUrl(null);
    }

    if (data.file_type.toLowerCase() === 'gif') {
      setGifPreviewLoading(true);
      try {
        const response = await fetch(getMediaPreviewUrl(data));
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(new Blob([blob], { type: 'image/gif' }));
        setGifPreviewUrl(objectUrl);
      } catch (err) {
        console.error('加载GIF预览失败:', err);
      } finally {
        setGifPreviewLoading(false);
      }
    }
  };

  const startEditAnnotation = (data: EvaluationData) => {
    setEditingAnnotation(data.id);
    setAnnotationText(data.annotation?.ground_truth || '');
  };

  const saveAnnotation = async (dataId: number) => {
    if (!annotationText.trim()) return;
    setSaving(true);
    try {
      const data = dataList.find(d => d.id === dataId);
      if (data?.annotation) {
        await annotationApi.update(data.annotation.id, { ground_truth: annotationText });
      } else {
        await annotationApi.create(dataId, { 
          ground_truth: annotationText, 
          annotation_type: 'manual' 
        });
      }
      setEditingAnnotation(null);
      setAnnotationText('');
      if (!removeRowIfFiltered(dataId)) {
        await fetchSingleData(dataId);
      }
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSaving(false);
    }
  };

  const handleAIAnnotate = async (dataId: number) => {
    setAiAnnotatingIds((prev) => new Set(prev).add(dataId));
    try {
      const result = await annotationApi.aiAnnotate({ data_ids: [dataId] });
      const taskId = result.task_id;
      
      const pollStatus = async () => {
        try {
          const status = await annotationApi.getAITaskStatus(taskId);
          if (status.status === 'completed') {
            setAiAnnotatingIds((prev) => {
              const next = new Set(prev);
              next.delete(dataId);
              return next;
            });
            if (!removeRowIfFiltered(dataId)) {
              await fetchSingleData(dataId);
            }
          } else {
            setTimeout(pollStatus, 2000);
          }
        } catch (err) {
          setAiAnnotatingIds((prev) => {
            const next = new Set(prev);
            next.delete(dataId);
            return next;
          });
          alert('查询标注状态失败: ' + (err instanceof Error ? err.message : '未知错误'));
        }
      };
      
      setTimeout(pollStatus, 2000);
    } catch (err) {
      setAiAnnotatingIds((prev) => {
        const next = new Set(prev);
        next.delete(dataId);
        return next;
      });
      alert('AI标注失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleDelete = async (dataId: number) => {
    if (!id || !confirm('确定要删除这条数据吗？')) return;
    try {
      await evaluationDataApi.delete(parseInt(id), dataId);
      fetchDataset();
    } catch (err) {
      alert('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleSaveBasics = async () => {
    if (!id || !nameValue.trim()) return;
    setSavingBasics(true);
    try {
      await datasetApi.update(parseInt(id), {
        name: nameValue.trim(),
        type: typeValue,
        scene: (sceneValue || undefined) as DatasetScene | undefined,
      });
      setEditingBasics(false);
      fetchDataset();
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSavingBasics(false);
    }
  };

  const handleSavePrompt = async () => {
    if (!id) return;
    setSavingPrompt(true);
    try {
      await datasetApi.update(parseInt(id), { annotation_prompt: promptValue || undefined });
      setEditingPrompt(false);
      fetchDataset();
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleSaveTags = async () => {
    if (!id) return;
    setSavingTags(true);
    try {
      const tags = tagsValue.split('\n').map(t => t.trim()).filter(t => t);
      await datasetApi.update(parseInt(id), { custom_tags: tags.length > 0 ? tags : undefined });
      setEditingTags(false);
      fetchDataset();
    } catch (err) {
      alert('保存失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setSavingTags(false);
    }
  };

  const isVideo = (fileType: string) => 
    ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'].includes(fileType.toLowerCase());

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
  };

  if (loading) {
    return <div className="p-6 text-center">加载中...</div>;
  }

  if (!dataset) {
    return <div className="p-6 text-center">评测集不存在</div>;
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <Link to="/datasets" className="text-blue-600 hover:text-blue-800">
          ← 返回评测集列表
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center space-x-2">
            {!editingBasics ? (
              <>
                <h1 className="text-2xl font-bold">{dataset.name}</h1>
                <button
                  onClick={() => {
                    setEditingBasics(true);
                    setNameValue(dataset.name);
                    setTypeValue(dataset.type);
                    setSceneValue(dataset.scene || '');
                  }}
                  className="text-gray-400 hover:text-gray-600 text-sm"
                >
                  ✏️ 编辑基础信息
                </button>
              </>
            ) : (
              <h1 className="text-2xl font-bold">编辑基础信息</h1>
            )}
          </div>
        </div>
        <p className="text-gray-600 mb-4">{dataset.description || '暂无描述'}</p>
        {editingBasics ? (
          <div className="mb-4 rounded-lg border bg-gray-50 p-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">评测集名称</label>
                <input
                  type="text"
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  placeholder="请输入评测集名称"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">评测集类型</label>
                <select
                  value={typeValue}
                  onChange={(e) => setTypeValue(e.target.value as DatasetType)}
                  className="w-full rounded border px-3 py-2 text-sm"
                >
                  <option value="video">视频类型</option>
                  <option value="image">图片类型</option>
                  <option value="mixed">图片+视频</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">业务场景</label>
                <select
                  value={sceneValue}
                  onChange={(e) => setSceneValue(e.target.value as DatasetScene | '')}
                  className="w-full rounded border px-3 py-2 text-sm"
                >
                  <option value="">请选择</option>
                  <option value="video_retrieval">录像检索</option>
                  <option value="smart_alert">智能消息告警</option>
                </select>
              </div>
            </div>
            <div className="mt-4 flex space-x-2">
              <button
                onClick={handleSaveBasics}
                disabled={savingBasics || !nameValue.trim()}
                className="px-3 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:bg-gray-400"
              >
                {savingBasics ? '保存中...' : '保存'}
              </button>
              <button
                onClick={() => {
                  setEditingBasics(false);
                  setNameValue('');
                  setTypeValue(dataset.type);
                  setSceneValue(dataset.scene || '');
                }}
                className="px-3 py-2 border rounded text-sm hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-4 text-sm items-center mb-4">
            <span className={`px-2 py-1 rounded ${
              dataset.type === 'video' ? 'bg-purple-100 text-purple-800' : 
              dataset.type === 'image' ? 'bg-green-100 text-green-800' : 
              'bg-blue-100 text-blue-800'
            }`}>
              {dataset.type === 'video' ? '视频类型' : dataset.type === 'image' ? '图片类型' : '图片+视频'}
            </span>
            {dataset.scene && (
              <span className={`px-2 py-1 rounded ${
                dataset.scene === 'video_retrieval' ? 'bg-orange-100 text-orange-800' : 
                'bg-teal-100 text-teal-800'
              }`}>
                {dataset.scene === 'video_retrieval' ? '录像检索' : '智能消息告警'}
              </span>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-4 text-sm items-center mb-4">
          <span className="text-gray-500">
            数据量: {dataset.data_count} | 已标注: {dataset.annotated_count}
          </span>
        </div>

        <div className="border-t pt-4 space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">标注提示词</span>
              {!editingPrompt && (
                <button
                  onClick={() => { setEditingPrompt(true); setPromptValue(dataset.annotation_prompt || ''); }}
                  className="text-blue-600 hover:text-blue-800 text-xs"
                >
                  {dataset.annotation_prompt ? '编辑' : '+ 添加提示词'}
                </button>
              )}
            </div>
            {editingPrompt ? (
              <div className="space-y-2">
                <textarea
                  value={promptValue}
                  onChange={(e) => setPromptValue(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-sm"
                  rows={4}
                  placeholder="输入标注提示词，用于指导AI标注..."
                />
                <div className="flex space-x-2">
                  <button
                    onClick={handleSavePrompt}
                    disabled={savingPrompt}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    {savingPrompt ? '保存中...' : '保存'}
                  </button>
                  <button
                    onClick={() => { setEditingPrompt(false); setPromptValue(''); }}
                    className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                {dataset.annotation_prompt ? (
                  <>
                    <p className={`whitespace-pre-wrap ${!expandedPrompt && dataset.annotation_prompt.length > 100 ? 'line-clamp-3' : ''}`}>
                      {dataset.annotation_prompt}
                    </p>
                    {dataset.annotation_prompt.length > 100 && (
                      <button
                        onClick={() => setExpandedPrompt(!expandedPrompt)}
                        className="text-blue-600 hover:text-blue-800 text-xs mt-1"
                      >
                        {expandedPrompt ? '收起' : '展开全部'}
                      </button>
                    )}
                  </>
                ) : (
                  '暂无标注提示词'
                )}
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">自定义标签</span>
              {!editingTags && (
                <button
                  onClick={() => { setEditingTags(true); setTagsValue((dataset.custom_tags || []).join('\n')); }}
                  className="text-blue-600 hover:text-blue-800 text-xs"
                >
                  {dataset.custom_tags && dataset.custom_tags.length > 0 ? '编辑' : '+ 添加标签'}
                </button>
              )}
            </div>
            {editingTags ? (
              <div className="space-y-2">
                <textarea
                  value={tagsValue}
                  onChange={(e) => setTagsValue(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-sm"
                  rows={3}
                  placeholder="输入标签，每行一个标签，例如：&#10;老人出现&#10;小孩出现&#10;骑电瓶车的人"
                />
                <div className="flex space-x-2">
                  <button
                    onClick={handleSaveTags}
                    disabled={savingTags}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    {savingTags ? '保存中...' : '保存'}
                  </button>
                  <button
                    onClick={() => { setEditingTags(false); setTagsValue(''); }}
                    className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {dataset.custom_tags && dataset.custom_tags.length > 0 ? (
                  dataset.custom_tags.map((tag, index) => (
                    <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-gray-500">暂无自定义标签</span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold">数据管理</h2>
              <span className="text-sm text-gray-500">当前评测集的数据与标注列表</span>
            </div>
          </div>
          <div className="flex flex-wrap items-stretch gap-3">
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
              <span className="text-xs font-medium text-gray-500">筛选</span>
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setDataPage(1);
                    setKeywordFilter(keywordInput.trim());
                  }
                }}
                placeholder="按对象名或标注结果筛选"
                className="w-56 rounded border px-3 py-2 text-sm"
              />
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as typeof statusFilter);
                  setDataPage(1);
                }}
                className="rounded border px-3 py-2 text-sm"
              >
                <option value="all">全部状态</option>
                <option value="pending">未标注</option>
                <option value="annotated">已标注</option>
                <option value="failed">失败</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  setDataPage(1);
                  setKeywordFilter(keywordInput.trim());
                }}
                className="px-3 py-2 rounded border text-sm hover:bg-gray-50"
              >
                筛选
              </button>
              <button
                type="button"
                onClick={() => {
                  setKeywordInput('');
                  setKeywordFilter('');
                  setStatusFilter('all');
                  setDataPage(1);
                }}
                className="px-3 py-2 rounded border text-sm hover:bg-gray-50"
              >
                重置
              </button>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
              <span className="text-xs font-medium text-gray-500">上传</span>
              <button
                onClick={() => setShowUploadModal(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                本地上传
              </button>
              <button
                onClick={openTOSModal}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                从TOS导入数据
              </button>
            </div>
          </div>
        </div>

        {dataList.length === 0 ? (
          <p className="text-gray-500 text-center py-4">暂无数据</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border px-4 py-2 text-left w-48">对象名称</th>
                  <th className="border px-4 py-2 text-left w-32">对象预览</th>
                  <th className="border px-4 py-2 text-left">标注结果</th>
                  <th className="border px-4 py-2 text-left w-40">更新时间</th>
                  <th className="border px-4 py-2 text-left w-40">操作</th>
                </tr>
              </thead>
              <tbody>
                {dataList.map((data) => (
                  <tr key={data.id} className="hover:bg-gray-50">
                      <td className="border px-4 py-2">
                        <div className="flex items-center">
                          <span className="text-lg mr-2">{isVideo(data.file_type) ? '🎬' : '🖼️'}</span>
                          <span className="truncate" title={data.file_name}>{data.file_name}</span>
                        </div>
                      </td>
                      <td className="border px-4 py-2">
                        <div 
                          className="w-16 h-16 bg-gray-100 rounded cursor-pointer overflow-hidden flex items-center justify-center"
                          onClick={() => openPreview(data)}
                        >
                          {isVideo(data.file_type) ? (
                            <video src={getMediaPreviewUrl(data)} className="max-w-full max-h-full object-contain" />
                          ) : (
                            <img src={getMediaPreviewUrl(data)} alt={data.file_name} className="max-w-full max-h-full object-contain" />
                          )}
                        </div>
                      </td>
                      <td className="border px-4 py-2">
                        {editingAnnotation === data.id ? (
                          <div className="space-y-2">
                            <textarea
                              value={annotationText}
                              onChange={(e) => setAnnotationText(e.target.value)}
                              className="w-full px-2 py-1 border rounded text-sm"
                              rows={3}
                              placeholder="输入标注内容..."
                            />
                            <div className="flex space-x-2">
                              <button
                                onClick={() => saveAnnotation(data.id)}
                                disabled={saving || !annotationText.trim()}
                                className="px-2 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:bg-gray-400"
                              >
                                {saving ? '保存中...' : '保存'}
                              </button>
                              <button
                                onClick={() => { setEditingAnnotation(null); setAnnotationText(''); }}
                                className="px-2 py-1 border rounded text-sm hover:bg-gray-50"
                              >
                                取消
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div 
                            className="cursor-pointer min-h-[60px] text-sm text-gray-600 hover:bg-gray-100 p-2 rounded"
                            onDoubleClick={() => startEditAnnotation(data)}
                            title="双击编辑"
                          >
                            {data.annotation?.ground_truth || <span className="text-gray-400">双击添加标注</span>}
                          </div>
                        )}
                      </td>
                      <td className="border px-4 py-2 text-sm text-gray-500">
                        {formatDateTime(data.updated_at || data.created_at)}
                      </td>
                      <td className="border px-4 py-2">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleAIAnnotate(data.id)}
                            disabled={aiAnnotatingIds.has(data.id)}
                            className="inline-flex items-center gap-2 whitespace-nowrap px-2 py-1 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:bg-gray-400"
                          >
                            {aiAnnotatingIds.has(data.id) ? (
                              <>
                                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                                <span className="whitespace-nowrap">标注中...</span>
                              </>
                            ) : (
                              '模型标注'
                            )}
                          </button>
                          <button
                            onClick={() => handleDelete(data.id)}
                            className="px-2 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
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
          
        {dataTotal > 0 && (
          <div className="flex justify-between items-center mt-4 pt-4 border-t">
            <div className="flex items-center space-x-2">
              <span className="text-gray-500 text-sm">共 {dataTotal} 条</span>
              <select
                value={dataPageSize}
                onChange={(e) => { setDataPageSize(Number(e.target.value) as 50 | 100); setDataPage(1); }}
                className="px-2 py-1 border rounded text-sm"
              >
                <option value={50}>50条/页</option>
                <option value={100}>100条/页</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setDataPage((p) => Math.max(1, p - 1))}
                disabled={dataPage === 1}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                上一页
              </button>
              <span className="px-3 py-1 text-sm">
                第 {dataPage} / {Math.ceil(dataTotal / dataPageSize)} 页
              </span>
              <button
                onClick={() => setDataPage((p) => Math.min(Math.ceil(dataTotal / dataPageSize), p + 1))}
                disabled={dataPage >= Math.ceil(dataTotal / dataPageSize)}
                className="px-3 py-1 border rounded text-sm disabled:opacity-50"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>

      {showPreviewModal && previewData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => {
          setShowPreviewModal(false);
          setPreviewData(null);
          if (gifPreviewUrl) {
            URL.revokeObjectURL(gifPreviewUrl);
            setGifPreviewUrl(null);
          }
        }}>
          <div className="bg-white rounded-lg shadow-lg max-w-4xl max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">{previewData.file_name}</h3>
              <button
                onClick={() => {
                  setShowPreviewModal(false);
                  setPreviewData(null);
                  if (gifPreviewUrl) {
                    URL.revokeObjectURL(gifPreviewUrl);
                    setGifPreviewUrl(null);
                  }
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <div className="p-4 flex items-center justify-center" style={{ maxHeight: '70vh' }}>
              {isVideo(previewData.file_type) ? (
                <video src={getMediaPreviewUrl(previewData)} className="max-w-full max-h-full" controls />
              ) : previewData.file_type.toLowerCase() === 'gif' ? (
                gifPreviewLoading ? (
                  <div className="text-sm text-gray-500">GIF 加载中...</div>
                ) : (
                  <img
                    src={gifPreviewUrl || getMediaPreviewUrl(previewData)}
                    alt={previewData.file_name}
                    className="max-w-full max-h-full object-contain"
                  />
                )
              ) : (
                <img 
                  src={getMediaPreviewUrl(previewData)} 
                  alt={previewData.file_name} 
                  className="max-w-full max-h-full object-contain" 
                />
              )}
            </div>
          </div>
        </div>
      )}

      {showTOSModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">从TOS导入数据</h3>
              <button onClick={() => setShowTOSModal(false)} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>
            
            <div className="p-4 border-b bg-gray-50">
              <div className="flex items-center space-x-2 text-sm">
                <span className="text-gray-500">桶: xujianhua-utils</span>
                <span className="text-gray-400">/</span>
                <span className="text-gray-500">AI-IPC</span>
                {tosPath.map((p, i) => (
                  <React.Fragment key={i}>
                    <span className="text-gray-400">/</span>
                    <span className="text-blue-600">{p}</span>
                  </React.Fragment>
                ))}
              </div>
            </div>

            <div className="p-4 overflow-auto" style={{ maxHeight: '400px' }}>
              {tosLoading ? (
                <div className="text-center py-8">加载中...</div>
              ) : (
                <>
                  {tosPath.length > 0 && (
                    <button onClick={goBack} className="mb-4 px-3 py-1 text-blue-600 hover:text-blue-800">
                      ← 返回上一级
                    </button>
                  )}
                  
                  {tosFolders.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm text-gray-500 mb-2">选择文件夹:</p>
                      {tosFolders.map((folder) => (
                        <div key={folder.prefix} className="flex items-center justify-between p-3 border rounded hover:bg-gray-50">
                          <div className="flex items-center">
                            <span className="text-2xl mr-3">📁</span>
                            <span>{folder.name}</span>
                          </div>
                          <div className="flex space-x-2">
                            <button onClick={() => navigateToFolder(folder)} className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800">
                              进入
                            </button>
                            <button onClick={() => selectFolderAndLoadFiles(folder)} className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200">
                              选择此文件夹
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {tosFiles.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm text-gray-500">
                          找到 {tosFiles.length} 个文件，已选择 {selectedFiles.size} 个
                        </p>
                        <button onClick={selectAllFiles} className="text-sm text-blue-600 hover:text-blue-800">
                          {selectedFiles.size === tosFiles.length ? '取消全选' : '全选'}
                        </button>
                      </div>
                      <div className="space-y-1">
                        {tosFiles.map((file) => (
                          <div
                            key={file.key}
                            onClick={() => toggleFileSelection(file.key)}
                            className={`flex items-center p-2 border rounded cursor-pointer ${
                              selectedFiles.has(file.key) ? 'bg-blue-50 border-blue-300' : 'hover:bg-gray-50'
                            }`}
                          >
                            <input type="checkbox" checked={selectedFiles.has(file.key)} onChange={() => {}} className="mr-3" />
                            <span className="text-xl mr-2">{isVideo(file.extension) ? '🎬' : '🖼️'}</span>
                            <span className="flex-1 truncate">{file.name}</span>
                            <span className="text-sm text-gray-400 ml-2">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {tosFolders.length === 0 && tosFiles.length === 0 && (
                    <div className="text-center py-8 text-gray-500">此文件夹为空</div>
                  )}
                </>
              )}
            </div>

            <div className="p-4 border-t flex justify-end space-x-3">
              <button onClick={() => setShowTOSModal(false)} className="px-4 py-2 border rounded hover:bg-gray-50">
                取消
              </button>
              <button
                onClick={handleImport}
                disabled={selectedFiles.size === 0 || importing}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {importing ? '导入中...' : `导入 ${selectedFiles.size} 个文件`}
              </button>
            </div>
          </div>
        </div>
      )}

      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg w-full max-w-xl max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold">本地上传文件</h3>
              <button onClick={() => setShowUploadModal(false)} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>
            <div className="p-4">
              <FileUpload
                datasetId={parseInt(id!)}
                datasetType={dataset.type as DatasetType}
                onUploadComplete={() => { setShowUploadModal(false); fetchDataset(); }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
