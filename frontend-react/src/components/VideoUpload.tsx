import React, { useState } from 'react';
import { API_BASE_URL } from '../config/api';
import { UploadResponse } from '../types';

interface VideoUploadProps {
  onVideosUploaded: (s3Keys: string[]) => void;
  onUploadStateChange: (uploading: boolean) => void;
}

const VideoUpload: React.FC<VideoUploadProps> = ({ onVideosUploaded, onUploadStateChange }) => {
  const [uploadedKeys, setUploadedKeys] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadItems, setUploadItems] = useState<Array<{
    name: string;
    progress: number;
    status: string;
  }>>([]);

  const getUploadUrl = async (filename: string, fileType: string): Promise<UploadResponse> => {
    const response = await fetch(`${API_BASE_URL}/generate-upload-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, fileType })
    });
    if (!response.ok) throw new Error(`Server error (${response.status})`);
    return response.json();
  };

  const uploadFileToS3 = (file: File, url: string, index: number): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          setUploadItems(prev => prev.map((item, i) => 
            i === index ? { ...item, progress: percentComplete, status: `Uploading... ${percentComplete}%` } : item
          ));
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          setUploadItems(prev => prev.map((item, i) => 
            i === index ? { ...item, status: 'Complete!' } : item
          ));
          resolve();
        } else {
          setUploadItems(prev => prev.map((item, i) => 
            i === index ? { ...item, status: `Failed (${xhr.status})` } : item
          ));
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        setUploadItems(prev => prev.map((item, i) => 
          i === index ? { ...item, status: 'Failed' } : item
        ));
        reject(new Error('Upload failed'));
      });

      xhr.open('PUT', url);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
  };

  const handleVideoUploads = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    onUploadStateChange(true);
    
    const fileArray = Array.from(files);
    setUploadItems(fileArray.map(file => ({
      name: file.name,
      progress: 0,
      status: 'Preparing...'
    })));

    const newKeys: string[] = [];

    try {
      for (let i = 0; i < fileArray.length; i++) {
        const file = fileArray[i];
        const { uploadUrl, s3Key } = await getUploadUrl(file.name, file.type);
        await uploadFileToS3(file, uploadUrl, i);
        newKeys.push(s3Key);
      }
      
      setUploadedKeys(prev => [...prev, ...newKeys]);
      onVideosUploaded([...uploadedKeys, ...newKeys]);
    } catch (error) {
      console.error('Video upload failed:', error);
    } finally {
      setIsUploading(false);
      onUploadStateChange(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="relative">
        <input
          className="hidden"
          type="file"
          id="videoFiles"
          accept=".mp4,.mov,.avi"
          multiple
          onChange={handleVideoUploads}
          disabled={isUploading}
        />
        <label
          htmlFor="videoFiles"
          className={`relative flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${
            isUploading 
              ? 'border-pink-300 bg-pink-50/50' 
              : 'border-gray-300 bg-white/50 hover:bg-pink-50/50 hover:border-pink-400'
          }`}
        >
          <div className="flex flex-col items-center justify-center pt-5 pb-6">
            <svg className="w-12 h-12 mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="mb-2 text-sm text-gray-500">
              <span className="font-semibold">Click to upload</span> your video clips
            </p>
            <p className="text-xs text-gray-500">MP4, MOV, or AVI • Multiple files supported</p>
          </div>
        </label>
      </div>
      
      {uploadItems.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-gray-700 flex items-center">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
            Upload Progress
          </h4>
          {uploadItems.map((item, index) => (
            <div key={index} className="bg-white/70 backdrop-blur-sm rounded-xl p-4 border border-white/20">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-pink-100 rounded-full flex items-center justify-center">
                    {item.status === 'Complete!' ? (
                      <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 text-pink-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{item.name}</p>
                    <p className="text-xs text-gray-500">{item.status}</p>
                  </div>
                </div>
                <div className="text-sm font-medium text-pink-600">{item.progress}%</div>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-pink-500 to-red-500 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${item.progress}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {uploadedKeys.length > 0 && (
        <div className="bg-green-50/70 backdrop-blur-sm rounded-xl p-4 border border-green-200">
          <div className="flex items-center mb-3">
            <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3">
              <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h4 className="font-semibold text-green-800">Videos Ready ({uploadedKeys.length})</h4>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {uploadedKeys.map((key, index) => (
              <div key={index} className="text-sm text-green-700 bg-white/50 rounded-lg px-3 py-2">
                {key.split('/').pop()}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoUpload;
