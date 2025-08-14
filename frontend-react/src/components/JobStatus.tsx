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
    <div className="space-y-6">
      <div className="text-center">
        <div className={`inline-flex items-center px-6 py-3 rounded-full text-lg font-bold ${
          status.status === 'SUCCESS' ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' :
          status.status === 'FAILURE' ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white' :
          'bg-gradient-to-r from-blue-500 to-purple-500 text-white'
        }`}>
          {status.status === 'SUCCESS' && (
            <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {status.status === 'FAILURE' && (
            <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {(status.status === 'QUEUED' || status.status === 'PROGRESS') && (
            <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
          )}
          Status: {status.status}
        </div>
      </div>
      
      {(status.status === 'QUEUED' || status.status === 'PROGRESS') && (
        <div className="bg-white/50 backdrop-blur-sm rounded-xl p-6 border border-white/20">
          <div className="flex justify-between items-center mb-4">
            <span className="text-lg font-semibold text-gray-700">Processing Progress</span>
            <span className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
              {status.progress}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
            <div 
              className="h-4 rounded-full transition-all duration-500 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500 animate-pulse" 
              style={{ width: `${status.progress}%` }}
            ></div>
          </div>
          <div className="mt-4 text-center">
            <p className="text-gray-600 font-medium">{status.message}</p>
          </div>
        </div>
      )}
      
      <div className="bg-white/50 backdrop-blur-sm rounded-xl p-6 border border-white/20">
        <div className="flex items-center mb-2">
          <svg className="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="font-semibold text-gray-700">Status Message</span>
        </div>
        <p className="text-gray-600 leading-relaxed">{status.message}</p>
      </div>
      
      {status.status === 'SUCCESS' && status.download_url && (
        <div className="text-center">
          <a 
            href={status.download_url} 
            className="inline-flex items-center px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold text-lg rounded-xl hover:from-green-600 hover:to-emerald-600 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl"
            download
          >
            <svg className="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Download Your Reel!
          </a>
        </div>
      )}
      
      {status.status === 'FAILURE' && (
        <div className="bg-gradient-to-r from-red-50 to-pink-50 backdrop-blur-sm rounded-xl p-6 border border-red-200">
          <div className="flex items-start">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mr-4 flex-shrink-0">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h4 className="text-red-800 font-bold text-lg mb-2">Processing Failed</h4>
              <p className="text-red-700 leading-relaxed">{status.message}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default JobStatus;
