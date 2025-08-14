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
  const [selectedDuration, setSelectedDuration] = useState<number>(15);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [timeDisplay, setTimeDisplay] = useState<string>('00:00 / 00:00');
  
  const waveformRef = useRef<HTMLDivElement>(null);
  const regionsPluginRef = useRef<any>(null);
  const isManualModeRef = useRef<boolean>(false);

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

      regionsPluginRef.current.on('region-created', (region: any) => {
        if (isManualMode) {
          setCurrentRegion(region);
          setSelectedDuration(Math.round((region.end - region.start) * 10) / 10);
          onSegmentSelected(region.start, region.end);
        }
      });

      regionsPluginRef.current.on('region-updated', (region: any) => {
        if (isManualMode) {
          setCurrentRegion(region);
          setSelectedDuration(Math.round((region.end - region.start) * 10) / 10);
          onSegmentSelected(region.start, region.end);
        }
      });

      ws.on('click', (relativeX: number) => {
        setTimeout(() => {
          if (isManualModeRef.current && regionsPluginRef.current) {
            const clickTime = relativeX * ws.getDuration();
            const regionDuration = Math.min(duration, ws.getDuration() - clickTime);
            
            regionsPluginRef.current.clearRegions();
            const newRegion = regionsPluginRef.current.addRegion({
              start: clickTime,
              end: clickTime + regionDuration,
              color: 'rgba(59, 130, 246, 0.25)',
              drag: true,
              resize: true
            });
            
            setCurrentRegion(newRegion);
            setSelectedDuration(Math.round(regionDuration * 10) / 10);
            onSegmentSelected(clickTime, clickTime + regionDuration);
          }
        }, 10);
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
      drag: isManualMode,
      resize: isManualMode
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
    const newManualMode = !isManualMode;
    setIsManualMode(newManualMode);
    isManualModeRef.current = newManualMode;
    
    if (regionsPluginRef.current) {
      regionsPluginRef.current.clearRegions();
      
      if (!newManualMode && aiSuggestions.length > 0) {
        displaySuggestion(currentSuggestionIndex);
        setSelectedDuration(duration);
      } else if (newManualMode) {
        setCurrentRegion(null);
        setSelectedDuration(duration);
      }
    }
  };

  const playPreview = () => {
    if (wavesurfer && currentRegion) {
      wavesurfer.play(currentRegion.start, currentRegion.end);
    }
  };

  if (!isVisible) return null;

  return (
    <div className="space-y-6">
      <div className="bg-white/30 backdrop-blur-sm rounded-xl p-4 border border-white/20">
        <div 
          ref={waveformRef} 
          className="rounded-lg bg-gradient-to-r from-purple-50 to-pink-50 p-4 min-h-[100px]"
        ></div>
      </div>
      
      <div className="flex items-center justify-center space-x-6">
        <button 
          className={`flex items-center space-x-2 px-6 py-3 rounded-xl font-medium transition-all duration-300 ${
            !currentRegion 
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed' 
              : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 shadow-lg hover:shadow-xl transform hover:scale-105'
          }`}
          onClick={playPreview}
          disabled={!currentRegion}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1.586a1 1 0 01.707.293l2.414 2.414a1 1 0 00.707.293H15M9 10v4a2 2 0 002 2h2a2 2 0 002-2v-4M9 10V9a2 2 0 012-2h2a2 2 0 012 2v1" />
          </svg>
          <span>Play Selection</span>
        </button>
        <div className="bg-white/70 backdrop-blur-sm rounded-xl px-4 py-2 border border-white/20">
          <div className="font-mono text-lg font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
            {timeDisplay}
          </div>
        </div>
      </div>

      <div className="bg-white/50 backdrop-blur-sm rounded-xl p-6 border border-white/20">
        <label htmlFor="durationSlider" className="block text-sm font-semibold text-gray-700 mb-4">
          Reel Duration: <span className="text-lg font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">{isManualMode ? selectedDuration : duration}</span> seconds
        </label>
        <input
          type="range"
          className="w-full h-3 bg-gradient-to-r from-purple-200 to-pink-200 rounded-lg appearance-none cursor-pointer slider"
          id="durationSlider"
          min="5"
          max="60"
          value={duration}
          onChange={(e) => handleDurationChange(parseInt(e.target.value))}
        />
        <div className="flex justify-between text-xs text-gray-500 mt-2">
          <span>5s</span>
          <span>30s</span>
          <span>60s</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 justify-center">
        <button 
          className="px-6 py-3 bg-white/70 backdrop-blur-sm border border-white/20 rounded-xl text-gray-700 hover:bg-white/90 transition-all duration-300 font-medium"
          onClick={toggleManualMode}
        >
          {isManualMode ? '🤖 Switch to AI Mode' : '✋ Switch to Manual Mode'}
        </button>
        
        {!isManualMode && (
          <>
            <button 
              className={`px-6 py-3 rounded-xl font-medium transition-all duration-300 ${
                isLoading 
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:from-blue-600 hover:to-purple-600 shadow-lg hover:shadow-xl transform hover:scale-105'
              }`}
              onClick={() => getNewAISuggestion(duration)}
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Finding...</span>
                </div>
              ) : (
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>Get New Suggestion</span>
                </div>
              )}
            </button>
            
            {aiSuggestions.length > 1 && (
              <div className="flex space-x-2">
                <button 
                  className="px-4 py-3 bg-white/70 backdrop-blur-sm border-2 border-purple-300 text-purple-700 rounded-xl hover:bg-purple-50 disabled:opacity-50 transition-all duration-300 font-medium"
                  onClick={() => {
                    const newIndex = Math.max(0, currentSuggestionIndex - 1);
                    setCurrentSuggestionIndex(newIndex);
                    displaySuggestion(newIndex);
                  }}
                  disabled={currentSuggestionIndex === 0}
                >
                  ← Previous
                </button>
                <button 
                  className="px-4 py-3 bg-white/70 backdrop-blur-sm border-2 border-purple-300 text-purple-700 rounded-xl hover:bg-purple-50 disabled:opacity-50 transition-all duration-300 font-medium"
                  onClick={() => {
                    const newIndex = Math.min(aiSuggestions.length - 1, currentSuggestionIndex + 1);
                    setCurrentSuggestionIndex(newIndex);
                    displaySuggestion(newIndex);
                  }}
                  disabled={currentSuggestionIndex === aiSuggestions.length - 1}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {!isManualMode && aiSuggestions[currentSuggestionIndex] && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 backdrop-blur-sm rounded-xl p-6 border border-blue-200">
          <div className="flex items-center mb-3">
            <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3">
              <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h4 className="font-bold text-blue-800">AI Suggestion</h4>
          </div>
          <p className="text-blue-700 leading-relaxed">{aiSuggestions[currentSuggestionIndex].reasoning}</p>
        </div>
      )}

      {isManualMode && (
        <div className="bg-gradient-to-r from-gray-50 to-blue-50 backdrop-blur-sm rounded-xl p-6 border border-gray-200">
          <div className="flex items-center mb-3">
            <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center mr-3">
              <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </div>
            <h4 className="font-bold text-gray-800">Manual Mode</h4>
          </div>
          <p className="text-gray-600 leading-relaxed italic">Click and drag on the waveform above to select your perfect audio segment.</p>
        </div>
      )}
    </div>
  );
};

export default AudioSelector;
