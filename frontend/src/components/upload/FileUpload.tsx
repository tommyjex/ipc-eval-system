import React, { useState } from 'react';
import { evaluationDataApi } from '../../api';
import type { DatasetType } from '../../api';

interface FileUploadProps {
  datasetId: number;
  datasetType: DatasetType;
  onUploadComplete: () => void;
}

const VIDEO_EXTENSIONS = ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'];
const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'];
const ALL_EXTENSIONS = [...VIDEO_EXTENSIONS, ...IMAGE_EXTENSIONS];
const MAX_VIDEO_SIZE = 500 * 1024 * 1024;
const MAX_IMAGE_SIZE = 20 * 1024 * 1024;

export const FileUpload: React.FC<FileUploadProps> = ({
  datasetId,
  datasetType,
  onUploadComplete,
}) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const getAllowedExtensions = (): string[] => {
    if (datasetType === 'video') return VIDEO_EXTENSIONS;
    if (datasetType === 'image') return IMAGE_EXTENSIONS;
    return ALL_EXTENSIONS;
  };

  const getMaxSize = (ext: string): number => {
    return VIDEO_EXTENSIONS.includes(ext) ? MAX_VIDEO_SIZE : MAX_IMAGE_SIZE;
  };

  const validateFile = (file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const allowedExtensions = getAllowedExtensions();
    
    if (!allowedExtensions.includes(ext)) {
      return `不支持的文件格式，支持: ${allowedExtensions.join(', ')}`;
    }
    
    const maxSize = getMaxSize(ext);
    if (file.size > maxSize) {
      return VIDEO_EXTENSIONS.includes(ext) 
        ? '视频文件大小不能超过500MB' 
        : '图片文件大小不能超过20MB';
    }
    return null;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    const newErrors: Record<string, string> = {};
    const validFiles: File[] = [];

    selectedFiles.forEach((file) => {
      const error = validateFile(file);
      if (error) {
        newErrors[file.name] = error;
      } else {
        validFiles.push(file);
      }
    });

    setErrors(newErrors);
    setFiles((prev) => [...prev, ...validFiles]);
  };

  const uploadFile = async (file: File): Promise<void> => {
    try {
      const presignedRes = await evaluationDataApi.getUploadUrl(datasetId, {
        file_name: file.name,
        file_type: file.name.split('.').pop() || '',
        file_size: file.size,
      });

      await fetch(presignedRes.upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': 'application/octet-stream',
        },
      });

      await evaluationDataApi.confirmUpload(datasetId, {
        file_name: file.name,
        file_type: file.name.split('.').pop() || '',
        file_size: file.size,
        tos_key: presignedRes.object_key,
        tos_bucket: 'evaluation-datasets',
      });

      setUploadProgress((prev) => ({ ...prev, [file.name]: 100 }));
    } catch (err) {
      setErrors((prev) => ({ ...prev, [file.name]: err instanceof Error ? err.message : '上传失败' }));
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    setUploadProgress({});

    await Promise.all(files.map(uploadFile));

    setUploading(false);
    setFiles([]);
    onUploadComplete();
  };

  const removeFile = (fileName: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== fileName));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[fileName];
      return next;
    });
  };

  const getAcceptTypes = (): string => {
    if (datasetType === 'video') return 'video/*';
    if (datasetType === 'image') return 'image/*';
    return 'video/*,image/*';
  };

  return (
    <div className="space-y-4">
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
        <input
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
          id="file-upload"
          accept={getAcceptTypes()}
        />
        <label
          htmlFor="file-upload"
          className="flex flex-col items-center justify-center cursor-pointer"
        >
          <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 17a4 4 0 01-4 4H7z" />
          </svg>
          <p className="mt-2 text-sm text-gray-600">
            点击或拖拽文件到此处上传
          </p>
          <p className="text-xs text-gray-500 mt-1">
            支持: {getAllowedExtensions().join(', ')} | 视频: 500MB | 图片: 20MB
          </p>
        </label>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.name} className="flex items-center justify-between bg-gray-50 p-3 rounded">
              <div className="flex items-center space-x-3">
                <span className="text-sm font-medium">{file.name}</span>
                <span className="text-xs text-gray-500">
                  {(file.size / 1024 / 1024).toFixed(2)}MB
                </span>
              </div>
              <div className="flex items-center space-x-2">
                {uploadProgress[file.name] !== undefined && (
                  <span className="text-xs text-green-600">已上传</span>
                )}
                {errors[file.name] && (
                  <span className="text-xs text-red-600">{errors[file.name]}</span>
                )}
                <button
                  onClick={() => removeFile(file.name)}
                  className="text-red-600 hover:text-red-800 text-sm"
                >
                  移除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={files.length === 0 || uploading}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
      >
        {uploading ? '上传中...' : '开始上传'}
      </button>
    </div>
  );
};
