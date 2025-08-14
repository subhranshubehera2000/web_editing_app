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
  const [theme, setTheme] = useState<string>('');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isCreatingReel, setIsCreatingReel] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(1);

  const handleAudioUploaded = (s3Key: string) => {
    setUploadedAudioS3Key(s3Key);
    setCurrentStep(2);
  };

  const handleVideosUploaded = (s3Keys: string[]) => {
    setUploadedVideoS3Keys(s3Keys);
    setCurrentStep(4);
  };

  const handleSegmentSelected = (start: number, end: number) => {
    setAudioSegmentStart(start);
    setAudioSegmentEnd(end);
    setCurrentStep(3);
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
    setCurrentStep(5);
    
    const payload = {
      audio_s3_key: uploadedAudioS3Key,
      video_s3_keys: uploadedVideoS3Keys,
      theme: theme || 'AI will suggest a theme',
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
        setCurrentStep(4);
      }
    } catch (error) {
      alert(`Error starting job: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsCreatingReel(false);
      setCurrentStep(4);
    }
  };

  const handleJobComplete = (downloadUrl?: string) => {
    setIsCreatingReel(false);
    if (downloadUrl) {
      console.log('Job completed successfully with download URL:', downloadUrl);
      setCurrentStep(6); // Move to completion step
    }
  };

  const canCreateReel = uploadedAudioS3Key && uploadedVideoS3Keys.length > 0 && !isUploading && !isCreatingReel;

  const steps = [
    { id: 1, name: 'Upload Audio', description: 'Upload your music track' },
    { id: 2, name: 'Select Segment', description: 'Choose the best part' },
    { id: 3, name: 'Upload Videos', description: 'Add your video clips' },
    { id: 4, name: 'Create Reel', description: 'Generate your masterpiece' },
    { id: 5, name: 'Processing', description: 'AI is working its magic' },
    { id: 6, name: 'Complete', description: 'Your reel is ready!' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      {/* Navigation */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-white/20 shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  AI Video Editor
                </h1>
                <p className="text-sm text-gray-500">Create stunning reels with AI</p>
              </div>
            </div>
            <div className="text-sm text-gray-600 bg-white/50 px-3 py-1 rounded-full">
              by Subhranshu Behera
            </div>
          </div>
        </div>
      </nav>

      {/* Progress Bar */}
      <div className="bg-white/50 backdrop-blur-sm border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className={`flex items-center ${index < steps.length - 1 ? 'flex-1' : ''}`}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${
                    currentStep >= step.id 
                      ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg' 
                      : 'bg-gray-200 text-gray-500'
                  }`}>
                    {currentStep > step.id ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      step.id
                    )}
                  </div>
                  <div className="ml-3 hidden sm:block">
                    <p className={`text-sm font-medium ${currentStep >= step.id ? 'text-blue-600' : 'text-gray-500'}`}>
                      {step.name}
                    </p>
                    <p className="text-xs text-gray-400">{step.description}</p>
                  </div>
                </div>
                {index < steps.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-4 transition-all duration-300 ${
                    currentStep > step.id ? 'bg-gradient-to-r from-blue-500 to-purple-500' : 'bg-gray-200'
                  }`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Upload and Audio Selection */}
          <div className="lg:col-span-2 space-y-8">
            {/* Step 1: Audio Upload */}
            <div className={`transform transition-all duration-500 ${currentStep >= 1 ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50'}`}>
              <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden">
                <div className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold text-white">Step 1: Upload Your Audio Track</h3>
                  </div>
                  <p className="text-blue-100 mt-2">Choose the perfect soundtrack for your reel</p>
                </div>
                <div className="p-6">
                  <AudioUpload 
                    onAudioUploaded={handleAudioUploaded}
                    onUploadStateChange={handleUploadStateChange}
                  />
                </div>
              </div>
            </div>
            
            {/* Step 2: Audio Selection */}
            {uploadedAudioS3Key && (
              <div className={`transform transition-all duration-500 ${currentStep >= 2 ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50'}`}>
                <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden">
                  <div className="bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <h3 className="text-xl font-bold text-white">Step 2: Select Audio Segment</h3>
                    </div>
                    <p className="text-purple-100 mt-2">Pick the most energetic part of your track</p>
                  </div>
                  <div className="p-6">
                    <AudioSelector
                      audioS3Key={uploadedAudioS3Key}
                      onSegmentSelected={handleSegmentSelected}
                      isVisible={!!uploadedAudioS3Key}
                    />
                  </div>
                </div>
              </div>
            )}
            
            {/* Step 3: Video Upload */}
            <div className={`transform transition-all duration-500 ${currentStep >= 3 ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50'}`}>
              <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden">
                <div className="bg-gradient-to-r from-pink-500 to-red-500 px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold text-white">Step 3: Upload Video Clips</h3>
                  </div>
                  <p className="text-pink-100 mt-2">Add your raw video footage for the reel</p>
                </div>
                <div className="p-6">
                  <VideoUpload 
                    onVideosUploaded={handleVideosUploaded}
                    onUploadStateChange={handleUploadStateChange}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Theme and Create */}
          <div className="space-y-8">
            {/* Step 4: Theme and Create */}
            <div className={`transform transition-all duration-500 ${currentStep >= 4 ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50'}`}>
              <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden">
                <div className="bg-gradient-to-r from-red-500 to-orange-500 px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold text-white">Step 4: Create Your Reel</h3>
                  </div>
                  <p className="text-red-100 mt-2">Define your style and let AI work its magic</p>
                </div>
                
                <div className="p-6 space-y-6">
                  <div>
                    <label htmlFor="theme" className="block text-sm font-semibold text-gray-700 mb-3">
                      Creative Theme (Optional)
                    </label>
                    <div className="relative">
                      <input 
                        type="text" 
                        className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all duration-200 bg-white/50 backdrop-blur-sm" 
                        id="theme" 
                        placeholder="e.g., Upbeat travel adventure, cinematic sunset vibes..."
                        value={theme}
                        onChange={(e) => setTheme(e.target.value)}
                      />
                      <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                        <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">Leave empty for AI to suggest the perfect theme based on your content</p>
                  </div>
                  
                  <button 
                    className={`w-full py-4 px-6 rounded-xl font-bold text-lg transition-all duration-300 transform ${
                      canCreateReel 
                        ? 'bg-gradient-to-r from-orange-500 to-red-500 text-white hover:from-orange-600 hover:to-red-600 hover:scale-105 shadow-lg hover:shadow-xl' 
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                    onClick={startEditing}
                    disabled={!canCreateReel}
                  >
                    {isCreatingReel ? (
                      <div className="flex items-center justify-center">
                        <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin mr-3"></div>
                        AI is Creating Your Reel...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center">
                        <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Create My Reel!
                      </div>
                    )}
                  </button>

                  {/* Upload Status Cards */}
                  <div className="space-y-3">
                    {uploadedAudioS3Key && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3">
                            <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-green-800">Audio Track Ready</p>
                            <p className="text-xs text-green-600">{uploadedAudioS3Key.split('/').pop()}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {uploadedVideoS3Keys.length > 0 && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                        <div className="flex items-center">
                          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3">
                            <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-blue-800">Video Clips Ready</p>
                            <p className="text-xs text-blue-600">{uploadedVideoS3Keys.length} file(s) uploaded</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Step 5: Job Status */}
            {currentJobId && (
              <div className={`transform transition-all duration-500 ${currentStep >= 5 ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50'}`}>
                <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden">
                  <div className={`bg-gradient-to-r px-6 py-4 ${
                    currentStep >= 6 
                      ? 'from-green-600 to-emerald-600' 
                      : 'from-purple-600 to-blue-600'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                        {currentStep >= 6 ? (
                          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        )}
                      </div>
                      <h3 className="text-xl font-bold text-white">
                        {currentStep >= 6 ? 'Reel Complete!' : 'AI Processing'}
                      </h3>
                    </div>
                    <p className="text-purple-100 mt-2">
                      {currentStep >= 6 
                        ? 'Your professional reel has been generated successfully' 
                        : 'Your reel is being crafted with AI precision'
                      }
                    </p>
                  </div>
                  <div className="p-6">
                    <JobStatus 
                      jobId={currentJobId}
                      onJobComplete={handleJobComplete}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gradient-to-r from-gray-900 via-blue-900 to-purple-900 text-white py-12 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="flex items-center justify-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-purple-400 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold">AI Video Editor</h3>
            </div>
            <p className="text-gray-300 mb-6 max-w-2xl mx-auto">
              Transform your raw footage into stunning reels with the power of artificial intelligence. 
              Powered by AWS Bedrock, advanced video processing, and creative AI direction.
            </p>
            <div className="flex items-center justify-center space-x-6 text-sm text-gray-400">
              <div className="flex items-center space-x-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>AI-Powered</span>
              </div>
              <div className="flex items-center space-x-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <span>Secure & Fast</span>
              </div>
              <div className="flex items-center space-x-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
                <span>Made with Love</span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
