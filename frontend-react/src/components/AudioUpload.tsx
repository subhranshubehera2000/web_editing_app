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
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="border-b pb-3 mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Step 1: Upload Your Media</h3>
      </div>
      <div className="space-y-4">
        <div>
          <label htmlFor="audioFile" className="block text-sm font-medium text-gray-700 mb-2">
            Audio Track (MP3, WAV)
          </label>
          <input
            ref={fileInputRef}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            type="file"
            id="audioFile"
            accept=".mp3,.wav,.aac"
            onChange={handleAudioUpload}
            disabled={isUploading}
          />
          {isUploading && (
            <div className="mt-3 p-3 bg-gray-50 rounded-md">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">{fileName}</span>
                <span className="text-sm text-gray-500">{uploadStatus}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AudioUpload;
