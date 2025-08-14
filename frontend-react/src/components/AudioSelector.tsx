import React, { useState, useEffect, useRef } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import { API_BASE_URL } from '../config/api';
import { AISuggestion } from '../types';

interface AudioSelectorProps {
  audioS3Key: string;
  onSegmentSelected: (start: number, end: number) => void;
  isVisible: boolean;
}

const AudioSelector: React.FC<AudioSelectorProps> = ({ audioS3Key, onSegmentSelected, isVisible }) => {
  const [wavesurfer, setWavesurfer] = useState<WaveSurfer | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion[]>([]);
  const [currentSuggestionIndex, setCurrentSuggestionIndex] = useState<number>(0);
  const [currentRegion, setCurrentRegion] = useState<any>(null);
  const [isManualMode, setIsManualMode] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(15);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [timeDisplay, setTimeDisplay] = useState<string>('00:00 / 00:00');
  
  const waveformRef = useRef<HTMLDivElement>(null);
  const regionsPluginRef = useRef<any>(null);

  useEffect(() => {
    if (isVisible && audioS3Key && waveformRef.current) {
      setupWaveform();
    }
    return () => {
      if (wavesurfer) {
        wavesurfer.destroy();
      }
    };
  }, [isVisible, audioS3Key]);

  const setupWaveform = async () => {
    try {
      const downloadResponse = await fetch(`${API_BASE_URL}/generate-download-url?s3_key=${audioS3Key}`);
      const downloadData = await downloadResponse.json();
      
      if (wavesurfer) {
        wavesurfer.destroy();
      }

      regionsPluginRef.current = RegionsPlugin.create();
      
      const ws = WaveSurfer.create({
        container: waveformRef.current!,
        waveColor: '#3b82f6',
        progressColor: '#1d4ed8',
        height: 80,
        plugins: [regionsPluginRef.current]
      });

      ws.load(downloadData.url);
      
      ws.on('ready', () => {
        setWavesurfer(ws);
        getNewAISuggestion(duration);
      });

      ws.on('timeupdate', (currentTime) => {
        const totalTime = ws.getDuration();
        setTimeDisplay(`${formatTime(currentTime)} / ${formatTime(totalTime)}`);
      });

    } catch (error) {
      console.error('Error setting up waveform:', error);
    }
  };

  const getNewAISuggestion = async (reelDuration: number) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/find-audio-segments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_s3_key: audioS3Key, reel_duration: reelDuration })
      });
      
      if (!response.ok) throw new Error(`Server suggestion failed (${response.status})`);
      
      const data = await response.json();
      const suggestions = data.ai_suggestions || [];
      setAiSuggestions(suggestions);
      
      if (suggestions.length > 0) {
        setCurrentSuggestionIndex(0);
        displaySuggestion(0, suggestions);
      }
    } catch (error) {
      console.error('Error getting AI suggestion:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const displaySuggestion = (index: number, suggestions: AISuggestion[] = aiSuggestions) => {
    const suggestion = suggestions[index];
    if (!suggestion || !regionsPluginRef.current) return;

    regionsPluginRef.current.clearRegions();
    
    const region = regionsPluginRef.current.addRegion({
      start: suggestion.start_time,
      end: suggestion.end_time,
      color: 'rgba(59, 130, 246, 0.25)',
      drag: false,
      resize: false
    });
    
    setCurrentRegion(region);
    onSegmentSelected(suggestion.start_time, suggestion.end_time);
  };

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleDurationChange = (newDuration: number) => {
    setDuration(newDuration);
    if (!isManualMode) {
      getNewAISuggestion(newDuration);
    }
  };

  const toggleManualMode = () => {
    setIsManualMode(!isManualMode);
    if (!isManualMode && regionsPluginRef.current) {
      regionsPluginRef.current.clearRegions();
    }
  };

  const playPreview = () => {
    if (wavesurfer && currentRegion) {
      wavesurfer.play(currentRegion.start, currentRegion.end);
    }
  };

  if (!isVisible) return null;

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="border-b pb-3 mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Step 2: Select Audio Segment & Reel Duration</h3>
      </div>
      
      <div className="space-y-4">
        <div 
          ref={waveformRef} 
          className="border border-gray-300 rounded-md bg-gray-50 p-2"
        ></div>
        
        <div className="flex items-center justify-center space-x-4">
          <button 
            className={`px-4 py-2 rounded-md font-medium ${
              !currentRegion 
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
            onClick={playPreview}
            disabled={!currentRegion}
          >
            ▶ Play Selection
          </button>
          <div className="font-mono text-lg font-semibold text-gray-700">{timeDisplay}</div>
        </div>

        <div className="space-y-2">
          <label htmlFor="durationSlider" className="block text-sm font-medium text-gray-700">
            Reel Duration: <span className="font-semibold text-blue-600">{duration}</span> seconds
          </label>
          <input
            type="range"
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            id="durationSlider"
            min="5"
            max="60"
            value={duration}
            onChange={(e) => handleDurationChange(parseInt(e.target.value))}
          />
        </div>

        <div className="flex flex-wrap gap-2 justify-center">
          <button 
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            onClick={toggleManualMode}
          >
            {isManualMode ? 'Switch to AI Mode' : 'Switch to Manual Mode'}
          </button>
          
          {!isManualMode && (
            <>
              <button 
                className={`px-4 py-2 rounded-md font-medium ${
                  isLoading 
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
                onClick={() => getNewAISuggestion(duration)}
                disabled={isLoading}
              >
                {isLoading ? 'Finding...' : 'Get New Suggestion'}
              </button>
              
              {aiSuggestions.length > 1 && (
                <div className="flex space-x-1">
                  <button 
                    className="px-3 py-2 border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 disabled:opacity-50"
                    onClick={() => {
                      const newIndex = Math.max(0, currentSuggestionIndex - 1);
                      setCurrentSuggestionIndex(newIndex);
                      displaySuggestion(newIndex);
                    }}
                    disabled={currentSuggestionIndex === 0}
                  >
                    Previous
                  </button>
                  <button 
                    className="px-3 py-2 border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 disabled:opacity-50"
                    onClick={() => {
                      const newIndex = Math.min(aiSuggestions.length - 1, currentSuggestionIndex + 1);
                      setCurrentSuggestionIndex(newIndex);
                      displaySuggestion(newIndex);
                    }}
                    disabled={currentSuggestionIndex === aiSuggestions.length - 1}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {!isManualMode && aiSuggestions[currentSuggestionIndex] && (
          <div className="p-4 bg-blue-50 rounded-md">
            <h4 className="font-medium text-blue-800 mb-2">AI Suggestion:</h4>
            <p className="text-blue-700">{aiSuggestions[currentSuggestionIndex].reasoning}</p>
          </div>
        )}

        {isManualMode && (
          <div className="p-4 bg-gray-50 rounded-md">
            <p className="text-gray-600 italic">Manual mode: Click and drag on the waveform to select your audio segment.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AudioSelector;
