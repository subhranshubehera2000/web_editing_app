export interface UploadProgress {
  loaded: number;
  total: number;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  download_url?: string;
}

export interface AISuggestion {
  start_time: number;
  end_time: number;
  reasoning: string;
}

export interface UploadResponse {
  uploadUrl: string;
  s3Key: string;
}
