const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
export const buildEvaluationDataPreviewUrl = (dataId: number) => `${API_BASE_URL}/datasets/data/${dataId}/preview`;

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  params?: Record<string, string | number | Array<string | number> | undefined>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    console.log('API Base URL:', this.baseUrl);
  }

  private buildUrl(path: string, params?: Record<string, string | number | Array<string | number> | undefined>): string {
    let urlStr = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          value.forEach((item) => {
            if (item !== undefined && item !== '') {
              searchParams.append(key, String(item));
            }
          });
        } else if (value !== undefined && value !== '') {
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
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      console.log('Response status:', response.status);

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '请求失败' }));
        if (response.status === 401 && !path.startsWith('/auth/')) {
          window.location.href = '/login';
        }
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

  async get<T>(path: string, params?: Record<string, string | number | Array<string | number> | undefined>): Promise<T> {
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

export interface AuthUser {
  username: string;
}

export type UserRole = 'admin' | 'user';
export type UserStatus = 'active' | 'disabled';

export interface User {
  id: number;
  username: string;
  nickname: string | null;
  role: UserRole;
  status: UserStatus;
  last_login_at: string | null;
  created_at: string;
  updated_at: string | null;
  deleted_at: string | null;
}

export interface UserListResponse {
  items: User[];
  total: number;
}

export interface UserCreateRequest {
  username: string;
  password: string;
  nickname?: string;
  role?: UserRole;
  status?: UserStatus;
}

export interface UserUpdateRequest {
  nickname?: string;
  role?: UserRole;
  status?: UserStatus;
}

export type DatasetType = 'video' | 'image' | 'mixed';
export type DatasetScene = 'video_retrieval' | 'smart_alert';
export type DatasetStatus = 'draft' | 'ready' | 'archived';
export type DatasetAnnotationStatus = 'pending' | 'partial' | 'annotated';
export type DataStatus = 'pending' | 'annotated' | 'failed';
export type AnnotationType = 'manual' | 'ai';

export interface Dataset {
  id: number;
  name: string;
  description: string | null;
  type: DatasetType;
  scene: DatasetScene | null;
  status: DatasetStatus;
  annotation_status: DatasetAnnotationStatus;
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
  list: (params?: { type?: DatasetType; annotation_status?: DatasetAnnotationStatus; keyword?: string; page?: number; page_size?: number }) =>
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
  list: (datasetId: number, params?: { status?: string; keyword?: string; page?: number; page_size?: number }) =>
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
export type TaskResultStatus = 'pending' | 'running' | 'completed' | 'failed';
export type TaskScoringStatus = 'not_scored' | 'scoring' | 'scored' | 'score_failed';

export type ModelProvider = 'volcengine' | 'aliyun' | 'gemini' | 'openai' | 'aws';

export interface EvaluationTask {
  id: number;
  dataset_id: number;
  name: string;
  target_model: string;
  model_provider: ModelProvider | null;
  scoring_criteria: string | null;
  prompt: string | null;
  fps: number;
  status: TaskStatus;
  avg_recall: number | null;
  avg_accuracy: number | null;
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
  prompt?: string;
  fps?: number;
}

export interface TaskResult {
  id: number;
  task_id: number;
  data_id: number;
  status: TaskResultStatus;
  model_output: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  score: number | null;
  recall: number | null;
  accuracy: number | null;
  score_reason: string | null;
  scoring_status: TaskScoringStatus;
  scoring_error_message: string | null;
  scoring_model: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
  scoring_started_at: string | null;
  scoring_completed_at: string | null;
}

export interface TaskResultDetail extends TaskResult {
  file_name: string;
  file_type: string;
  download_url: string | null;
  ground_truth: string | null;
}

export interface TaskResultDetailListResponse {
  items: TaskResultDetail[];
  total: number;
  avg_recall: number | null;
  avg_accuracy: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
}

export interface TaskResultSelectionResponse {
  total: number;
  result_ids: number[];
  data_ids: number[];
}

export interface ScoringTemplate {
  id: number;
  name: string;
  scene: DatasetScene;
  description: string | null;
  content: string;
  created_at: string;
  updated_at: string | null;
}

export interface ScoringTemplateListResponse {
  items: ScoringTemplate[];
  total: number;
}

export interface PromptTemplate {
  id: number;
  name: string;
  scene: DatasetScene;
  description: string | null;
  content: string;
  created_at: string;
  updated_at: string | null;
}

export interface PromptTemplateListResponse {
  items: PromptTemplate[];
  total: number;
}

export const taskApi = {
  list: (params?: { dataset_id?: number[]; model_provider?: ModelProvider[]; target_model?: string[]; status?: TaskStatus[]; sort_by?: 'avg_recall' | 'avg_accuracy'; sort_order?: 'asc' | 'desc'; page?: number; page_size?: number }) =>
    api.get<{ items: EvaluationTask[]; total: number }>('/tasks', params),
  get: (taskId: number) =>
    api.get<EvaluationTask>(`/tasks/${taskId}`),
  create: (data: EvaluationTaskCreate) =>
    api.post<EvaluationTask>('/tasks', data),
  update: (taskId: number, data: Partial<EvaluationTaskCreate & { status: TaskStatus }>) =>
    api.put<EvaluationTask>(`/tasks/${taskId}`, data),
  delete: (taskId: number) =>
    api.delete(`/tasks/${taskId}`),
  run: (taskId: number, data?: { data_ids?: number[] }) =>
    api.post<{ message: string; task_id: number }>(`/tasks/${taskId}/run`, data || {}),
  score: (taskId: number, data?: { result_ids?: number[] }) =>
    api.post<{ message: string; task_id: number; scored_count: number; skipped_count: number; failed_count: number; model: string }>(`/tasks/${taskId}/score`, data || {}),
  getResults: (taskId: number, params?: { page?: number; page_size?: number }) =>
    api.get<{ items: TaskResult[]; total: number }>(`/tasks/${taskId}/results`, params),
  getResultsDetail: (taskId: number, params?: { page?: number; page_size?: number; status?: TaskResultStatus[]; scoring_status?: TaskScoringStatus[] }) =>
    api.get<TaskResultDetailListResponse>(`/tasks/${taskId}/results/detail`, params),
  getResultSelection: (taskId: number, params?: { status?: TaskResultStatus[]; scoring_status?: TaskScoringStatus[] }) =>
    api.get<TaskResultSelectionResponse>(`/tasks/${taskId}/results/selection`, params),
};

export const authApi = {
  login: (payload: { username: string; password: string }) => api.post<AuthUser>('/auth/login', payload),
  logout: () => api.post<void>('/auth/logout', {}),
  me: () => api.get<AuthUser>('/auth/me'),
};

export const userApi = {
  list: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    api.get<UserListResponse>('/users', params),
  get: (userId: number) =>
    api.get<User>(`/users/${userId}`),
  create: (data: UserCreateRequest) =>
    api.post<User>('/users', data),
  update: (userId: number, data: UserUpdateRequest) =>
    api.put<User>(`/users/${userId}`, data),
  resetPassword: (userId: number, data: { password: string }) =>
    api.post<User>(`/users/${userId}/reset-password`, data),
  delete: (userId: number) =>
    api.delete<void>(`/users/${userId}`),
};

export const scoringTemplateApi = {
  list: (params?: { scene?: DatasetScene }) =>
    api.get<ScoringTemplateListResponse>('/scoring-templates', params),
  create: (data: { name: string; scene: DatasetScene; description?: string; content: string }) =>
    api.post<ScoringTemplate>('/scoring-templates', data),
  update: (templateId: number, data: Partial<{ name: string; scene: DatasetScene; description: string; content: string }>) =>
    api.put<ScoringTemplate>(`/scoring-templates/${templateId}`, data),
  delete: (templateId: number) =>
    api.delete<{ message: string }>(`/scoring-templates/${templateId}`),
};

export const promptTemplateApi = {
  list: (params?: { scene?: DatasetScene }) =>
    api.get<PromptTemplateListResponse>('/prompt-templates', params),
  create: (data: { name: string; scene: DatasetScene; description?: string; content: string }) =>
    api.post<PromptTemplate>('/prompt-templates', data),
  update: (templateId: number, data: Partial<{ name: string; scene: DatasetScene; description: string; content: string }>) =>
    api.put<PromptTemplate>(`/prompt-templates/${templateId}`, data),
  delete: (templateId: number) =>
    api.delete<{ message: string }>(`/prompt-templates/${templateId}`),
};
