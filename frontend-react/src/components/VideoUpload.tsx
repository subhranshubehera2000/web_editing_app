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
    <div className="space-y-4">
      <div>
        <label htmlFor="videoFiles" className="block text-sm font-medium text-gray-700 mb-2">
          Video Files (MP4, MOV)
        </label>
        <input
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          type="file"
          id="videoFiles"
          accept=".mp4,.mov,.avi"
          multiple
          onChange={handleVideoUploads}
          disabled={isUploading}
        />
      </div>
      
      {uploadItems.length > 0 && (
        <div className="space-y-3">
          {uploadItems.map((item, index) => (
            <div key={index} className="p-3 bg-gray-50 rounded-md">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">{item.name}</span>
                <span className="text-sm text-gray-500">{item.status}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${item.progress}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {uploadedKeys.length > 0 && (
        <div className="mt-4 p-4 bg-green-50 rounded-md">
          <h4 className="font-medium text-green-800 mb-2">Uploaded Videos:</h4>
          <ul className="space-y-1">
            {uploadedKeys.map((key, index) => (
              <li key={index} className="text-sm text-green-700">{key.split('/').pop()}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default VideoUpload;
