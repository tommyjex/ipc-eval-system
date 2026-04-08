const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  params?: Record<string, string | number | undefined>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    console.log('API Base URL:', this.baseUrl);
  }

  private buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
    let urlStr = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          searchParams.append(key, String(value));
        }
      });
      if (searchParams.toString()) {
        urlStr += `?${searchParams.toString()}`;
      }
    }
    console.log('Request URL:', urlStr);
    return urlStr;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, params } = options;
    const url = this.buildUrl(path, params);

    console.log('Request options:', { method, body });

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      console.log('Response status:', response.status);

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(error.detail || `请求失败: ${response.status}`);
      }

      if (response.status === 204) {
        return {} as T;
      }

      return response.json();
    } catch (err) {
      if (err instanceof Error) {
        console.error('API Error:', err.message);
        throw err;
      }
      throw new Error('未知错误');
    }
  }

  async get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
    return this.request<T>(path, { params });
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body });
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }
}

export const api = new ApiClient(API_BASE_URL);

export type DatasetType = 'video' | 'image' | 'mixed';
export type DatasetScene = 'video_retrieval' | 'smart_alert';
export type DatasetStatus = 'draft' | 'ready' | 'archived';
export type DataStatus = 'pending' | 'annotated' | 'failed';
export type AnnotationType = 'manual' | 'ai';

export interface Dataset {
  id: number;
  name: string;
  description: string | null;
  type: DatasetType;
  scene: DatasetScene | null;
  status: DatasetStatus;
  data_count: number;
  annotated_count: number;
  created_at: string;
  updated_at: string | null;
  annotation_prompt: string | null;
  custom_tags: string[] | null;
}

export interface DatasetListResponse {
  items: Dataset[];
  total: number;
}

export interface DatasetCreate {
  name: string;
  description?: string;
  type: DatasetType;
  scene?: DatasetScene;
}

export interface EvaluationData {
  id: number;
  dataset_id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  tos_key: string;
  tos_bucket: string;
  status: DataStatus;
  created_at: string;
  download_url: string | null;
  annotation: Annotation | null;
  updated_at: string | null;
}

export interface EvaluationDataListResponse {
  items: EvaluationData[];
  total: number;
}

export interface PresignedUrlResponse {
  upload_url: string;
  object_key: string;
  expires_in: number;
}

export interface Annotation {
  id: number;
  data_id: number;
  ground_truth: string;
  annotation_type: AnnotationType;
  model_name: string | null;
  annotator_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface TOSFolder {
  name: string;
  prefix: string;
  full_path: string;
}

export interface TOSFolderListResponse {
  folders: TOSFolder[];
  current_prefix: string;
}

export interface TOSFile {
  key: string;
  name: string;
  size: number;
  extension: string;
  last_modified: string;
  selected?: boolean;
}

export interface TOSFileListResponse {
  files: TOSFile[];
  folder_prefix: string;
}

export const datasetApi = {
  list: (params?: { type?: string; status?: string; keyword?: string; page?: number; page_size?: number }) =>
    api.get<DatasetListResponse>('/datasets', params),
  get: (id: number) => api.get<Dataset>(`/datasets/${id}`),
  create: (data: DatasetCreate) => api.post<Dataset>('/datasets', data),
  update: (id: number, data: Partial<Dataset>) => api.put<Dataset>(`/datasets/${id}`, data),
  delete: (id: number) => api.delete(`/datasets/${id}`),
};

export const evaluationDataApi = {
  getUploadUrl: (datasetId: number, data: { file_name: string; file_type: string; file_size: number }) =>
    api.post<PresignedUrlResponse>(`/datasets/${datasetId}/upload-url`, data),
  confirmUpload: (datasetId: number, data: { file_name: string; file_type: string; file_size: number; tos_key: string; tos_bucket: string }) =>
    api.post<EvaluationData>(`/datasets/${datasetId}/data`, data),
  list: (datasetId: number, params?: { status?: string; page?: number; page_size?: number }) =>
    api.get<EvaluationDataListResponse>(`/datasets/${datasetId}/data`, params),
  delete: (datasetId: number, dataId: number) =>
    api.delete(`/datasets/${datasetId}/data/${dataId}`),
  getTOSFolders: (datasetId: number, prefix?: string) =>
    api.get<TOSFolderListResponse>(`/datasets/${datasetId}/tos-folders`, { prefix }),
  getTOSFiles: (datasetId: number, prefix: string) =>
    api.get<TOSFileListResponse>(`/datasets/${datasetId}/tos-files`, { prefix }),
  importFromTOS: (datasetId: number, keys: string[]) =>
    api.post<EvaluationData[]>(`/datasets/${datasetId}/import-v2`, { keys }),
};

export const annotationApi = {
  create: (dataId: number, data: { ground_truth: string; annotation_type: AnnotationType }) =>
    api.post<Annotation>(`/data/${dataId}/annotations`, data),
  batchCreate: (data: { data_ids: number[]; ground_truth: string }) =>
    api.post<Annotation[]>('/batch-annotations', data),
  get: (dataId: number) => api.get<Annotation>(`/data/${dataId}/annotations`),
  update: (annotationId: number, data: { ground_truth: string }) =>
    api.put<Annotation>(`/annotations/${annotationId}`, data),
  aiAnnotate: (data: { data_ids: number[]; model?: string; prompt?: string }) =>
    api.post<AIAnnotationStatus>('/ai-annotations', data),
  getAITaskStatus: (taskId: string) =>
    api.get<AIAnnotationStatus>(`/ai-annotations/${taskId}`),
};

export interface AIAnnotationStatus {
  task_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

export type ModelProvider = 'volcengine' | 'aliyun' | 'gemini' | 'openai' | 'aws';

export interface EvaluationTask {
  id: number;
  dataset_id: number;
  name: string;
  target_model: string;
  model_provider: ModelProvider | null;
  scoring_criteria: string | null;
  status: TaskStatus;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
}

export interface EvaluationTaskCreate {
  dataset_id: number;
  name: string;
  target_model: string;
  model_provider?: ModelProvider;
  scoring_criteria?: string;
}

export interface TaskResult {
  id: number;
  task_id: number;
  data_id: number;
  model_output: string | null;
  score: number | null;
  score_reason: string | null;
  created_at: string;
}

export interface TaskResultDetail extends TaskResult {
  file_name: string;
  file_type: string;
  download_url: string | null;
  ground_truth: string | null;
}

export const taskApi = {
  list: (params?: { dataset_id?: number; status?: TaskStatus; page?: number; page_size?: number }) =>
    api.get<{ items: EvaluationTask[]; total: number }>('/tasks', params),
  get: (taskId: number) =>
    api.get<EvaluationTask>(`/tasks/${taskId}`),
  create: (data: EvaluationTaskCreate) =>
    api.post<EvaluationTask>('/tasks', data),
  update: (taskId: number, data: Partial<EvaluationTaskCreate & { status: TaskStatus }>) =>
    api.put<EvaluationTask>(`/tasks/${taskId}`, data),
  delete: (taskId: number) =>
    api.delete(`/tasks/${taskId}`),
  run: (taskId: number) =>
    api.post<{ message: string; task_id: number }>(`/tasks/${taskId}/run`),
  getResults: (taskId: number, params?: { page?: number; page_size?: number }) =>
    api.get<{ items: TaskResult[]; total: number }>(`/tasks/${taskId}/results`, params),
  getResultsDetail: (taskId: number, params?: { page?: number; page_size?: number }) =>
    api.get<TaskResultDetail[]>(`/tasks/${taskId}/results/detail`, params),
};
