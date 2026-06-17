import React, { useEffect, useMemo, useState } from 'react';
import { vectorRetrievalApi } from '../../api';
import type {
  VectorCollection,
  VectorIndex,
  VectorRetrievalEvaluateResponse,
  VectorRetrievalResultItem,
} from '../../api';

const RERANK_MODELS = ['m3-v2-rerank', 'base-multilingual-rerank'] as const;
type RerankModel = (typeof RERANK_MODELS)[number];
const RESULT_PAGE_SIZE = 10;

const formatScore = (score: number | null) => {
  if (score === null || score === undefined) {
    return '-';
  }
  return Number.isInteger(score) ? String(score) : score.toFixed(6);
};

const formatJson = (value: unknown) => JSON.stringify(value, null, 2);

const metadataValueToText = (value: unknown) => {
  if (value === null || value === undefined || value === '') {
    return '';
  }
  if (Array.isArray(value)) {
    return value.filter(Boolean).join('；');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};

const collectTruncatedObjectIds = (response: VectorRetrievalEvaluateResponse) => {
  const finalObjectIds = new Set(response.final_results.map((item) => item.object_id));
  return new Set(
    response.rerank_results
      .filter((item) => item.kept === false || !finalObjectIds.has(item.object_id))
      .map((item) => item.object_id),
  );
};

function ResultContentCard({ item }: { item: VectorRetrievalResultItem }) {
  const title = metadataValueToText(item.metadata.title);
  const description = metadataValueToText(item.metadata.description);
  const event = metadataValueToText(item.metadata.event);
  const des = metadataValueToText(item.metadata.des);
  const hasStructuredContent = Boolean(title || description || event || des);

  return (
    <div className="w-full rounded-xl border border-blue-100 bg-blue-50/50 p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="break-words text-sm font-semibold leading-6 text-gray-900">
            {item.object_name || item.object_id}
          </div>
          <div className="mt-1 break-all font-mono text-xs text-gray-500">{item.object_id}</div>
        </div>
      </div>

      {hasStructuredContent ? (
        <div className="mt-3 space-y-2 text-sm leading-6 text-gray-700">
          {title && (
            <div>
              <span className="font-medium text-gray-900">标题：</span>
              <span className="break-words">{title}</span>
            </div>
          )}
          {description && (
            <div>
              <span className="font-medium text-gray-900">描述：</span>
              <span className="break-words">{description}</span>
            </div>
          )}
          {event && (
            <div>
              <span className="font-medium text-gray-900">事件：</span>
              <span className="break-words">{event}</span>
            </div>
          )}
          {des && (
            <details className="rounded-lg bg-white/70 px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-blue-700 hover:text-blue-900">
                展开拼接内容
              </summary>
              <div className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-gray-700">{des}</div>
            </details>
          )}
        </div>
      ) : (
        <div className="mt-3 text-sm leading-6 text-gray-500">暂无可展示的元素句内容</div>
      )}
    </div>
  );
}

function ResultSection({
  title,
  description,
  results,
  rankField,
  showRerankScore,
  currentPage,
  onPageChange,
  markedObjectIds,
  finalObjectIds,
  onRowDoubleClick,
}: {
  title: string;
  description: string;
  results: VectorRetrievalResultItem[];
  rankField: 'rank' | 'rerank_rank';
  showRerankScore: boolean;
  currentPage: number;
  onPageChange: (page: number) => void;
  markedObjectIds: Set<string>;
  finalObjectIds: Set<string>;
  onRowDoubleClick: (event: React.MouseEvent<HTMLTableRowElement>, item: VectorRetrievalResultItem) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(results.length / RESULT_PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const startIndex = (safePage - 1) * RESULT_PAGE_SIZE;
  const paginatedResults = results.slice(startIndex, startIndex + RESULT_PAGE_SIZE);

  return (
    <section className="rounded-lg bg-white p-5 shadow">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <p className="mt-1 text-sm text-gray-500">{description}</p>
        </div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-600">{results.length} 条</span>
      </div>

      {results.length === 0 ? (
        <div className="rounded border border-dashed border-gray-200 py-8 text-center text-gray-500">
          暂无检索结果
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] table-fixed text-sm">
            <colgroup>
              <col className="w-[72px]" />
              <col className="w-[66%]" />
              <col className="w-[120px]" />
              {showRerankScore && <col className="w-[130px]" />}
            </colgroup>
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-3 py-3">排序</th>
                <th className="px-3 py-3">元数据</th>
                <th className="px-3 py-3">Search 分数</th>
                {showRerankScore && <th className="px-3 py-3">Rerank 分数</th>}
              </tr>
            </thead>
            <tbody>
              {paginatedResults.map((item, index) => {
                const isMarked = markedObjectIds.has(item.object_id);
                const rowHighlightClass = isMarked
                  ? finalObjectIds.has(item.object_id)
                    ? 'bg-green-100 hover:bg-green-100'
                    : 'bg-red-100 hover:bg-red-100'
                  : 'hover:bg-gray-50';

                return (
                  <tr
                    key={`${item.object_id}-${index}`}
                    onDoubleClick={(event) => onRowDoubleClick(event, item)}
                    className={`cursor-pointer border-t align-top ${rowHighlightClass}`}
                    title="鼠标左键双击标记或取消标记该条结果"
                  >
                    <td className="whitespace-nowrap px-3 py-3 text-gray-700">
                      {item[rankField] ?? startIndex + index + 1}
                    </td>
                    <td className="px-3 py-3">
                      <ResultContentCard item={item} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 font-mono text-gray-700">
                      {formatScore(item.search_score)}
                    </td>
                    {showRerankScore && (
                      <td className="whitespace-nowrap px-3 py-3 font-mono text-gray-700">
                        {formatScore(item.rerank_score)}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {results.length > RESULT_PAGE_SIZE && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
              <span className="text-gray-500">
                每页最多 {RESULT_PAGE_SIZE} 条，当前显示 {startIndex + 1}-
                {Math.min(startIndex + RESULT_PAGE_SIZE, results.length)} 条
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onPageChange(Math.max(1, safePage - 1))}
                  disabled={safePage === 1}
                  className="rounded border px-3 py-1 text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  上一页
                </button>
                <span className="px-2 text-gray-600">
                  第 {safePage} / {totalPages} 页
                </span>
                <button
                  type="button"
                  onClick={() => onPageChange(Math.min(totalPages, safePage + 1))}
                  disabled={safePage === totalPages}
                  className="rounded border px-3 py-1 text-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export const VectorRetrievalEvaluationPage: React.FC = () => {
  const [collections, setCollections] = useState<VectorCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [collectionName, setCollectionName] = useState('');
  const [indexes, setIndexes] = useState<VectorIndex[]>([]);
  const [indexesLoading, setIndexesLoading] = useState(false);
  const [indexName, setIndexName] = useState('');
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(10);
  const [rerankModel, setRerankModel] = useState<RerankModel>('m3-v2-rerank');
  const [minScoreInput, setMinScoreInput] = useState('');
  const [stepDeltaThresholdInput, setStepDeltaThresholdInput] = useState('');
  const [filterInput, setFilterInput] = useState('');
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterError, setFilterError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<VectorRetrievalEvaluateResponse | null>(null);
  const [searchPage, setSearchPage] = useState(1);
  const [rerankPage, setRerankPage] = useState(1);
  const [finalPage, setFinalPage] = useState(1);
  const [markedObjectIds, setMarkedObjectIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchCollections = async () => {
      setCollectionsLoading(true);
      try {
        const response = await vectorRetrievalApi.listCollections();
        setCollections(response);
        if (response.length > 0) {
          setCollectionName(response[0].collection_name);
        }
      } catch (error) {
        setSubmitError(error instanceof Error ? error.message : '获取向量数据集列表失败');
      } finally {
        setCollectionsLoading(false);
      }
    };

    fetchCollections();
  }, []);

  const selectedCollection = useMemo(
    () => collections.find((collection) => collection.collection_name === collectionName) || null,
    [collections, collectionName],
  );

  useEffect(() => {
    if (!collectionName) {
      setIndexes([]);
      setIndexName('');
      return;
    }

    const fetchIndexes = async () => {
      setIndexesLoading(true);
      setIndexName('');
      try {
        const response = await vectorRetrievalApi.listIndexes({ collection_name: collectionName });
        setIndexes(response);
        setIndexName(response[0]?.index_name || '');
      } catch (error) {
        setIndexes([]);
        setSubmitError(error instanceof Error ? error.message : '获取 Index 列表失败');
      } finally {
        setIndexesLoading(false);
      }
    };

    fetchIndexes();
  }, [collectionName]);

  const addFilterTag = () => {
    const tag = filterInput.trim();
    if (!tag) {
      return;
    }
    if (filterTags.includes(tag)) {
      setFilterError('过滤标签已存在');
      return;
    }
    setFilterTags((prev) => [...prev, tag]);
    setFilterInput('');
    setFilterError('');
  };

  const handleFilterInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addFilterTag();
    }
  };

  const parseOptionalThreshold = (value: string, label: string, allowNegative = true) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      throw new Error(`${label}必须为数字`);
    }
    if (!allowNegative && parsed < 0) {
      throw new Error(`${label}不能小于 0`);
    }
    return parsed;
  };

  const handleSubmit = async () => {
    if (!collectionName) {
      setSubmitError('请选择向量数据集');
      return;
    }

    if (!query.trim()) {
      setSubmitError('请输入搜索 query');
      return;
    }

    if (!indexName) {
      setSubmitError('当前 Collection 无可用 Index，请先选择其他 Collection');
      return;
    }

    if (topK < 1 || topK > 100) {
      setSubmitError('top_k 必须在 1 到 100 之间');
      return;
    }

    let minScore: number | undefined;
    let stepDeltaThreshold: number | undefined;
    try {
      minScore = parseOptionalThreshold(minScoreInput, '低分截断阈值');
      stepDeltaThreshold = parseOptionalThreshold(stepDeltaThresholdInput, 'step delta 阈值', false);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '截断阈值输入非法');
      return;
    }

    setSubmitting(true);
    setSubmitError('');
    try {
      const response = await vectorRetrievalApi.evaluate({
        collection_name: collectionName,
        index_name: indexName,
        query: query.trim(),
        top_k: topK,
        rerank_model: rerankModel,
        filter_tags: filterTags,
        min_score: minScore,
        step_delta_threshold: stepDeltaThreshold,
      });
      setResult(response);
      setSearchPage(1);
      setRerankPage(1);
      setFinalPage(1);
      setMarkedObjectIds(collectTruncatedObjectIds(response));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '向量检索评估失败');
    } finally {
      setSubmitting(false);
    }
  };

  const finalObjectIds = useMemo(
    () => new Set(result?.final_results.map((item) => item.object_id) || []),
    [result],
  );

  const handleResultRowDoubleClick = (
    event: React.MouseEvent<HTMLTableRowElement>,
    item: VectorRetrievalResultItem,
  ) => {
    if (event.button !== 0) {
      return;
    }
    setMarkedObjectIds((prev) => {
      const next = new Set(prev);
      if (next.has(item.object_id)) {
        next.delete(item.object_id);
      } else {
        next.add(item.object_id);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">向量检索效果评估</h1>
        <p className="mt-2 text-sm text-gray-600">
          基于 VikingDB Collection 和文字 query 发起检索，并展示 search、rerank 与截断后的最终结果。
        </p>
      </div>

      <section className="rounded-lg bg-white p-5 shadow">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4 xl:grid-cols-7">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">向量数据集</span>
            <select
              value={collectionName}
              onChange={(event) => setCollectionName(event.target.value)}
              disabled={collectionsLoading || submitting}
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            >
              {collectionsLoading ? (
                <option value="">加载中...</option>
              ) : collections.length === 0 ? (
                <option value="">暂无向量数据集</option>
              ) : (
                collections.map((collection) => (
                  <option key={collection.collection_name} value={collection.collection_name}>
                    {collection.collection_name}
                    {collection.data_count !== null ? `（${collection.data_count} 条）` : ''}
                  </option>
                ))
              )}
            </select>
            {selectedCollection && (
              <span className="mt-1 block text-xs text-gray-500">
                {selectedCollection.data_count !== null ? `数据量：${selectedCollection.data_count}` : '已选择 Collection'}
              </span>
            )}
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">Index</span>
            <select
              value={indexName}
              onChange={(event) => setIndexName(event.target.value)}
              disabled={indexesLoading || submitting || !collectionName}
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            >
              {indexesLoading ? (
                <option value="">加载中...</option>
              ) : indexes.length === 0 ? (
                <option value="">暂无可用 Index</option>
              ) : (
                indexes.map((index) => (
                  <option key={index.index_name} value={index.index_name}>
                    {index.index_name}
                    {index.status ? `（${index.status}）` : ''}
                  </option>
                ))
              )}
            </select>
            <span className="mt-1 block text-xs text-gray-500">Collection 切换后自动刷新</span>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">搜索 query</span>
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              disabled={submitting}
              placeholder="请输入要检索的文字"
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">top_k</span>
            <input
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
              disabled={submitting}
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            />
            <span className="mt-1 block text-xs text-gray-500">后端限制范围为 1 到 100</span>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">Rerank 模型</span>
            <select
              value={rerankModel}
              onChange={(event) => setRerankModel(event.target.value as RerankModel)}
              disabled={submitting}
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            >
              {RERANK_MODELS.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-xs text-gray-500">调用 Viking 知识库 Rerank 接口</span>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">低分截断阈值</span>
            <input
              type="number"
              min={0}
              step="any"
              value={minScoreInput}
              onChange={(event) => setMinScoreInput(event.target.value)}
              disabled={submitting}
              placeholder="留空使用后端配置"
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            />
            <span className="mt-1 block text-xs text-gray-500">留空时不提交 min_score</span>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-gray-700">step delta 阈值</span>
            <input
              type="number"
              step="any"
              value={stepDeltaThresholdInput}
              onChange={(event) => setStepDeltaThresholdInput(event.target.value)}
              disabled={submitting}
              placeholder="留空使用后端配置"
              className="w-full rounded border px-3 py-2 disabled:bg-gray-100"
            />
            <span className="mt-1 block text-xs text-gray-500">
              按 (当前分数 - 下一条分数) / 当前分数 计算；下降 30% 填 0.3
            </span>
          </label>
        </div>

        <label className="mt-4 block">
          <span className="mb-2 block text-sm font-medium text-gray-700">标量过滤标签</span>
          <input
            type="text"
            value={filterInput}
            onChange={(event) => {
              setFilterInput(event.target.value);
              setFilterError('');
            }}
            onKeyDown={handleFilterInputKeyDown}
            onBlur={addFilterTag}
            disabled={submitting}
            placeholder="输入标签后按回车，例如 person、car、pet"
            className={`w-full rounded border px-3 py-2 text-sm disabled:bg-gray-100 ${
              filterError ? 'border-red-400' : 'border-gray-300'
            }`}
          />
          {filterTags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {filterTags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => setFilterTags((prev) => prev.filter((item) => item !== tag))}
                    className="text-blue-500 hover:text-blue-800"
                    aria-label={`删除过滤标签 ${tag}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </label>

        {filterError && <div className="mt-2 text-sm text-red-600">{filterError}</div>}

        <div className="mt-4">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={
              submitting || collectionsLoading || indexesLoading || !collectionName || !indexName || !query.trim()
            }
            className="w-full rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300 sm:w-auto"
          >
            {submitting ? '检索中...' : '检索'}
          </button>
        </div>

        {submitError && (
          <div className="mt-4 flex items-center justify-between gap-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{submitError}</span>
            <button type="button" onClick={handleSubmit} className="shrink-0 text-red-700 underline">
              重试
            </button>
          </div>
        )}
      </section>

      {result && (
        <section className="rounded-lg bg-white p-5 shadow">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-7">
            <div>
              <div className="text-sm text-gray-500">搜索 query</div>
              <div className="mt-1 font-medium text-gray-900">{result.query.file_name}</div>
              <div className="mt-1 text-xs text-gray-500">Collection: {result.collection_name || '-'}</div>
              <div className="mt-1 text-xs text-gray-500">Index: {result.index_name || '-'}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">请求 top_k</div>
              <div className="mt-1 font-medium text-gray-900">{result.top_k}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Rerank 模型</div>
              <div className="mt-1 font-medium text-gray-900">{result.rerank_model}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">截断状态</div>
              <div className="mt-1 font-medium text-gray-900">
                {result.truncated ? `已截断：${result.truncate_reason || '命中策略'}` : '未截断'}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">最终保留</div>
              <div className="mt-1 font-medium text-gray-900">{result.final_results.length} 条</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">低分阈值</div>
              <div className="mt-1 font-medium text-gray-900">{formatScore(result.min_score)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">step delta 阈值</div>
              <div className="mt-1 font-medium text-gray-900">{formatScore(result.step_delta_threshold)}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-start gap-4">
            <details className="min-w-[260px] flex-1">
              <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-800">
                查看提交过滤条件和多模态输入
              </summary>
              <pre className="mt-2 max-h-64 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
                {formatJson({
                  scalar_filter: result.scalar_filter,
                  post_process_ops: result.post_process_ops,
                  rerank_model: result.rerank_model,
                  collection_name: result.collection_name,
                  index_name: result.index_name,
                  multimodal_input: result.query.multimodal_input,
                  min_score: result.min_score,
                  step_delta_threshold: result.step_delta_threshold,
                })}
              </pre>
            </details>
          </div>
        </section>
      )}

      {result && (
        <div className="space-y-6">
          <div className="rounded-xl border-2 border-amber-300 bg-amber-50 px-5 py-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="shrink-0 text-base font-semibold text-amber-900">背景色标记说明</span>
              <span className="inline-flex items-center gap-2 rounded-full border border-green-300 bg-green-100 px-3 py-1 font-medium text-green-800">
                <span className="h-3 w-3 rounded-full bg-green-500" />
                绿色：同时存在于 Search、Rerank 和最终结果
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-red-300 bg-red-100 px-3 py-1 font-medium text-red-800">
                <span className="h-3 w-3 rounded-full bg-red-500" />
                红色：被截断或未进入最终结果
              </span>
              <span className="inline-flex items-center rounded-full border border-amber-300 bg-white px-3 py-1 font-medium text-amber-900">
                鼠标左键双击结果行可手动标记或取消标记
              </span>
            </div>
          </div>
          <ResultSection
            title="Search 原始结果"
            description="VikingDB search_by_multi_modal 返回的原始候选顺序。"
            results={result.search_results}
            rankField="rank"
            showRerankScore={false}
            currentPage={searchPage}
            onPageChange={setSearchPage}
            markedObjectIds={markedObjectIds}
            finalObjectIds={finalObjectIds}
            onRowDoubleClick={handleResultRowDoubleClick}
          />
          <ResultSection
            title="Rerank 排序结果"
            description="候选结果按 rerank 分数重新排序，并标记后续截断状态。"
            results={result.rerank_results}
            rankField="rerank_rank"
            showRerankScore
            currentPage={rerankPage}
            onPageChange={setRerankPage}
            markedObjectIds={markedObjectIds}
            finalObjectIds={finalObjectIds}
            onRowDoubleClick={handleResultRowDoubleClick}
          />
          <ResultSection
            title="截断后最终结果"
            description="仅展示通过低分阈值与 step delta 策略后最终保留的结果。"
            results={result.final_results}
            rankField="rerank_rank"
            showRerankScore
            currentPage={finalPage}
            onPageChange={setFinalPage}
            markedObjectIds={markedObjectIds}
            finalObjectIds={finalObjectIds}
            onRowDoubleClick={handleResultRowDoubleClick}
          />
        </div>
      )}
    </div>
  );
};
