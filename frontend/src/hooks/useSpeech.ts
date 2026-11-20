import { useState, useCallback, useRef, useEffect } from 'react';
import { transcribeAudio, fetchSpeechHealth } from '../lib/api';

export type SpeechState = 'idle' | 'recording' | 'transcribing';

export function useSpeech() {
  const [state, setState] = useState<SpeechState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef('');
  const recognitionErrorRef = useRef<string | null>(null);
  const recognitionEndedRef = useRef(false);
  const recognitionStopRequestedRef = useRef(false);

  // Prefer Android/WebView native Speech Recognition for Marathi.
  // Keep the existing backend recorder as a fallback on browsers without it.
  useEffect(() => {
    const NativeRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (NativeRecognition) {
      setAvailable(true);
      return;
    }
    fetchSpeechHealth()
      .then((health) => setAvailable(health.available))
      .catch(() => setAvailable(false));
  }, []);

  const startRecording = useCallback(async (): Promise<void> => {
    setError(null);
    transcriptRef.current = '';
    recognitionErrorRef.current = null;
    recognitionEndedRef.current = false;
    recognitionStopRequestedRef.current = false;

    const NativeRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (NativeRecognition) {
      try {
        const recognition = new NativeRecognition();
        recognition.lang = 'mr-IN';
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.onresult = (event: any) => {
          let text = '';
          for (let i = event.resultIndex || 0; i < event.results.length; i++) {
            text += event.results[i][0]?.transcript || '';
          }
          if (text.trim()) transcriptRef.current = text.trim();
        };
        recognition.onerror = (event: any) => {
          recognitionErrorRef.current = event.error || 'Marathi speech recognition failed';
        };
        recognition.onend = () => {
          recognitionEndedRef.current = true;
          if (!recognitionStopRequestedRef.current) setState('idle');
        };
        recognitionRef.current = recognition;
        recognition.start();
        setState('recording');
        return;
      } catch (err) {
        recognitionRef.current = null;
        const msg = err instanceof Error ? err.message : 'Speech recognition could not start';
        setError(msg);
        setState('idle');
        return;
      }
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone not supported in this browser');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setState('recording');
    } catch (err) {
      setError('Microphone access denied');
      setState('idle');
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<string> => {
    const nativeRecognition = recognitionRef.current;
    if (nativeRecognition) {
      setState('transcribing');
      recognitionStopRequestedRef.current = true;
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          const text = transcriptRef.current.trim();
          const error = recognitionErrorRef.current;
          recognitionRef.current = null;
          recognitionStopRequestedRef.current = false;
          setState('idle');
          if (text) resolve(text);
          else reject(new Error(error ? `Speech recognition: ${error}` : 'आवाज समजला नाही. पुन्हा प्रयत्न करा.'));
        };
        if (recognitionEndedRef.current) {
          finish();
          return;
        }
        nativeRecognition.onend = finish;
        try { nativeRecognition.stop(); } catch { finish(); }
      });
    }
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state !== 'recording') {
        reject(new Error('Not recording'));
        return;
      }

      recorder.onstop = async () => {
        setState('transcribing');

        // Stop all audio tracks
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        chunksRef.current = [];

        try {
          const result = await transcribeAudio(blob);
          setState('idle');
          resolve(result.text);
        } catch (err) {
          setState('idle');
          const msg = err instanceof Error ? err.message : 'Transcription failed';
          setError(msg);
          reject(err);
        }
      };

      recorder.stop();
    });
  }, []);

  return {
    state,
    error,
    available,
    startRecording,
    stopRecording,
    isRecording: state === 'recording',
    isTranscribing: state === 'transcribing',
  };
}
