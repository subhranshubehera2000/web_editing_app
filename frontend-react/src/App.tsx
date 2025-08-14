import { useState } from 'react';
import AudioUpload from './components/AudioUpload';
import VideoUpload from './components/VideoUpload';
import AudioSelector from './components/AudioSelector';
import JobStatus from './components/JobStatus';
import { API_BASE_URL } from './config/api';

function App() {
  const [uploadedAudioS3Key, setUploadedAudioS3Key] = useState<string>('');
  const [uploadedVideoS3Keys, setUploadedVideoS3Keys] = useState<string[]>([]);
  const [audioSegmentStart, setAudioSegmentStart] = useState<number>(0);
  const [audioSegmentEnd, setAudioSegmentEnd] = useState<number>(15);
  const [theme, setTheme] = useState<string>('AI will suggest a theme');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isCreatingReel, setIsCreatingReel] = useState<boolean>(false);

  const handleAudioUploaded = (s3Key: string) => {
    setUploadedAudioS3Key(s3Key);
  };

  const handleVideosUploaded = (s3Keys: string[]) => {
    setUploadedVideoS3Keys(s3Keys);
  };

  const handleSegmentSelected = (start: number, end: number) => {
    setAudioSegmentStart(start);
    setAudioSegmentEnd(end);
  };

  const handleUploadStateChange = (uploading: boolean) => {
    setIsUploading(uploading);
  };

  const startEditing = async () => {
    if (!uploadedAudioS3Key || uploadedVideoS3Keys.length === 0) {
      alert('Please upload audio and video files first.');
      return;
    }

    setIsCreatingReel(true);
    
    const payload = {
      audio_s3_key: uploadedAudioS3Key,
      video_s3_keys: uploadedVideoS3Keys,
      theme: theme,
      audio_start_sec: audioSegmentStart,
      audio_end_sec: audioSegmentEnd
    };

    try {
      const response = await fetch(`${API_BASE_URL}/start-edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (response.ok) {
        setCurrentJobId(data.job_id);
      } else {
        alert(`Error starting job: ${data.error || 'Unknown error'}`);
        setIsCreatingReel(false);
      }
    } catch (error) {
      alert(`Error starting job: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsCreatingReel(false);
    }
  };

  const handleJobComplete = (downloadUrl?: string) => {
    setIsCreatingReel(false);
    if (downloadUrl) {
      console.log('Job completed successfully with download URL:', downloadUrl);
    }
  };

  const canCreateReel = uploadedAudioS3Key && uploadedVideoS3Keys.length > 0 && !isUploading && !isCreatingReel;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-gradient-to-r from-blue-600 to-blue-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-white">
                AI Video Editor ✨
              </h1>
            </div>
            <div className="text-sm text-blue-100">
              developed by Subhranshu Behera
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Upload and Audio Selection */}
          <div className="lg:col-span-2 space-y-6">
            <AudioUpload 
              onAudioUploaded={handleAudioUploaded}
              onUploadStateChange={handleUploadStateChange}
            />
            
            {uploadedAudioS3Key && (
              <AudioSelector
                audioS3Key={uploadedAudioS3Key}
                onSegmentSelected={handleSegmentSelected}
                isVisible={!!uploadedAudioS3Key}
              />
            )}
            
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="border-b pb-3 mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Step 3: Upload Video Files</h3>
              </div>
              <VideoUpload 
                onVideosUploaded={handleVideosUploaded}
                onUploadStateChange={handleUploadStateChange}
              />
            </div>
          </div>

          {/* Right Column - Theme and Create */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="border-b pb-3 mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Step 4: Define Theme & Create</h3>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label htmlFor="theme" className="block text-sm font-medium text-gray-700 mb-2">
                    Reel Theme (Optional)
                  </label>
                  <input 
                    type="text" 
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                    id="theme" 
                    placeholder="e.g., Upbeat travel, cinematic"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                  />
                </div>
                
                <button 
                  className={`w-full py-3 px-4 rounded-md font-medium text-lg ${
                    canCreateReel 
                      ? 'bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2' 
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  } transition-colors`}
                  onClick={startEditing}
                  disabled={!canCreateReel}
                >
                  {isCreatingReel ? (
                    <div className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Processing...
                    </div>
                  ) : (
                    '🚀 Create Reel!'
                  )}
                </button>

                {/* Upload Status */}
                {uploadedAudioS3Key && (
                  <div className="text-sm text-gray-600">
                    <div className="flex items-center">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span><strong>Audio:</strong> {uploadedAudioS3Key.split('/').pop()}</span>
                    </div>
                  </div>
                )}

                {uploadedVideoS3Keys.length > 0 && (
                  <div className="text-sm text-gray-600">
                    <div className="flex items-center">
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span><strong>Videos:</strong> {uploadedVideoS3Keys.length} file(s) uploaded</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {currentJobId && (
              <JobStatus 
                jobId={currentJobId}
                onJobComplete={handleJobComplete}
              />
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-gray-300">AI Video Editor - Powered by AWS Bedrock & Advanced Video Processing</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
