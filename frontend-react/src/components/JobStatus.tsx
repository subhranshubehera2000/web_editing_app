import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';
import { JobStatus as JobStatusType } from '../types';

interface JobStatusProps {
  jobId: string | null;
  onJobComplete: (downloadUrl?: string) => void;
}

const JobStatus: React.FC<JobStatusProps> = ({ jobId, onJobComplete }) => {
  const [status, setStatus] = useState<JobStatusType | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  useEffect(() => {
    if (jobId && !isPolling) {
      setIsPolling(true);
      const interval = setInterval(() => checkJobStatus(jobId), 3000);
      
      return () => {
        clearInterval(interval);
        setIsPolling(false);
      };
    }
  }, [jobId]);

  const checkJobStatus = async (id: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/job-status?job_id=${id}`);
      if (!response.ok) return;
      
      const data: JobStatusType = await response.json();
      setStatus(data);
      
      if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
        setIsPolling(false);
        onJobComplete(data.download_url);
      }
    } catch (error) {
      console.error('Error fetching job status:', error);
      setIsPolling(false);
    }
  };

  if (!status) return null;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mt-4">
      <div className="border-b pb-3 mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Job Status</h3>
      </div>
      
      <div className="space-y-4">
        <div>
          <span className="font-medium text-gray-700">Status: </span>
          <span className={`px-2 py-1 rounded-full text-sm font-medium ${
            status.status === 'SUCCESS' ? 'bg-green-100 text-green-800' :
            status.status === 'FAILURE' ? 'bg-red-100 text-red-800' :
            'bg-blue-100 text-blue-800'
          }`}>
            {status.status}
          </span>
        </div>
        
        {(status.status === 'QUEUED' || status.status === 'PROGRESS') && (
          <div>
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>Progress</span>
              <span>{status.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300 animate-pulse" 
                style={{ width: `${status.progress}%` }}
              ></div>
            </div>
          </div>
        )}
        
        <div>
          <span className="font-medium text-gray-700">Message: </span>
          <span className="text-gray-600">{status.message}</span>
        </div>
        
        {status.status === 'SUCCESS' && status.download_url && (
          <div className="pt-4">
            <a 
              href={status.download_url} 
              className="inline-flex items-center px-6 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors"
              download
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Your Reel!
            </a>
          </div>
        )}
        
        {status.status === 'FAILURE' && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <div className="flex">
              <svg className="w-5 h-5 text-red-400 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h4 className="text-red-800 font-medium">Processing Failed</h4>
                <p className="text-red-700 mt-1">{status.message}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default JobStatus;
