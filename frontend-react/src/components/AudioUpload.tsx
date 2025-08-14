import React, { useState, useRef } from 'react';
import { API_BASE_URL } from '../config/api';
import { UploadResponse } from '../types';

interface AudioUploadProps {
  onAudioUploaded: (s3Key: string) => void;
  onUploadStateChange: (uploading: boolean) => void;
}

const AudioUpload: React.FC<AudioUploadProps> = ({ onAudioUploaded, onUploadStateChange }) => {
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [fileName, setFileName] = useState<string>('');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getUploadUrl = async (filename: string, fileType: string): Promise<UploadResponse> => {
    const response = await fetch(`${API_BASE_URL}/generate-upload-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, fileType })
    });
    if (!response.ok) throw new Error(`Server error (${response.status})`);
    return response.json();
  };

  const uploadFileToS3 = (file: File, url: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          setUploadProgress(percentComplete);
          setUploadStatus(`Uploading... ${percentComplete}%`);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          setUploadStatus('Upload complete!');
          resolve();
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'));
      });

      xhr.open('PUT', url);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
  };

  const handleAudioUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    onUploadStateChange(true);
    setFileName(file.name);
    setUploadProgress(0);
    setUploadStatus('Preparing upload...');

    try {
      const { uploadUrl, s3Key } = await getUploadUrl(file.name, file.type);
      await uploadFileToS3(file, uploadUrl);
      onAudioUploaded(s3Key);
    } catch (error) {
      setUploadStatus(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
      onUploadStateChange(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="relative">
        <input
          ref={fileInputRef}
          className="hidden"
          type="file"
          id="audioFile"
          accept=".mp3,.wav,.aac"
          onChange={handleAudioUpload}
          disabled={isUploading}
        />
        <label
          htmlFor="audioFile"
          className={`relative flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${
            isUploading 
              ? 'border-blue-300 bg-blue-50/50' 
              : 'border-gray-300 bg-white/50 hover:bg-blue-50/50 hover:border-blue-400'
          }`}
        >
          <div className="flex flex-col items-center justify-center pt-5 pb-6">
            <svg className="w-10 h-10 mb-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
            <p className="mb-2 text-sm text-gray-500">
              <span className="font-semibold">Click to upload</span> your audio track
            </p>
            <p className="text-xs text-gray-500">MP3, WAV, or AAC (MAX. 50MB)</p>
          </div>
        </label>
      </div>

      {isUploading && (
        <div className="bg-white/70 backdrop-blur-sm rounded-xl p-4 border border-white/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{fileName}</p>
                <p className="text-xs text-gray-500">{uploadStatus}</p>
              </div>
            </div>
            <div className="text-sm font-medium text-blue-600">{uploadProgress}%</div>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-300" 
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AudioUpload;
