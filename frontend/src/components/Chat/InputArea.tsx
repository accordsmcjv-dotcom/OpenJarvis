import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Square, Paperclip, Search, Camera, X } from 'lucide-react';
import { toast } from 'sonner';
import { useAppStore, generateId } from '../../lib/store';
import { streamChat, streamResearch } from '../../lib/sse';
import { apiFetch, fetchSavings, getBase } from '../../lib/api';
import { listConnectors, getSyncStatus } from '../../lib/connectors-api';
import { serializeToolCallArguments } from '../../lib/tool-call';
import { findShivamContacts, placeShivamCall, openShivamMessageComposer, sendShivamSms, searchShivamYouTube, type ShivamContact } from '../../lib/shivam-calls';
import {
  engineFromCompletionChunk,
  resolveChatEngine,
} from '../../lib/chat-telemetry';
import { MicButton } from './MicButton';
import { useTtsStore } from '../../lib/tts';
import { useSpeech } from '../../hooks/useSpeech';

interface ShivamNavigationApi {
  openNavigation(options: { destination: string; mode: 'driving' | 'bicycling' | 'walking' }): Promise<{ opened: boolean; travelMode: string }>;
  startWatchman(): Promise<{ started: boolean }>;
  stopWatchman(): Promise<{ stopping: boolean }>;
}
const ShivamNavigation = registerPlugin<ShivamNavigationApi>('ShivamDevice');
import { registerPlugin } from '@capacitor/core';

interface ShivamWakeWordApi { startListening(): Promise<void>; stopListening(): Promise<void>; }
const ShivamWakeWord = registerPlugin<ShivamWakeWordApi>('ShivamWakeWord');

type ShivamWakeStatus = 'listening' | 'capturing' | 'thinking' | 'off';
function announceWakeStatus(status: ShivamWakeStatus) {
  window.dispatchEvent(new CustomEvent('shivamWakeStatus', { detail: status }));
}
async function startWakeWordListening() {
  try {
    await ShivamWakeWord.startListening();
    announceWakeStatus('listening');
  } catch {
    announceWakeStatus('off');
  }
}
async function stopWakeWordListening() {
  try {
    await ShivamWakeWord.stopListening();
  } finally {
    announceWakeStatus('off');
  }
}
import type {
  ChatMessage,
  MessageTelemetry,
  ResearchSearchTrace,
  ResearchSource,
  TokenUsage,
  ToolCallInfo,
} from '../../types';

// While Deep Research is toggled on, poll connected sources for sync
// progress so we can surface "Searching over N items — sync in progress"
// next to the toggle. Polling is gated on `enabled` so toggling DR off
// stops the network chatter immediately.
function useResearchCorpusSync(enabled: boolean): {
  syncing: boolean;
  itemsSynced: number;
} {
  const [state, setState] = useState({ syncing: false, itemsSynced: 0 });

  useEffect(() => {
    if (!enabled) {
      setState({ syncing: false, itemsSynced: 0 });
      return;
    }
    let cancelled = false;

    const poll = async () => {
      try {
        const list = await listConnectors();
        const connected = list.filter((c) => c.connected);
        if (connected.length === 0) {
          if (!cancelled) setState({ syncing: false, itemsSynced: 0 });
          return;
        }
        const results = await Promise.all(
          connected.map(async (c) => {
            try {
              return await getSyncStatus(c.connector_id);
            } catch {
              return null;
            }
          }),
        );
        let syncing = false;
        let itemsSynced = 0;
        for (const r of results) {
          if (!r) continue;
          if (r.state === 'syncing') syncing = true;
          itemsSynced += r.items_synced ?? 0;
        }
        if (!cancelled) setState({ syncing, itemsSynced });
      } catch {
        // Network blip — leave previous state intact.
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [enabled]);

  return state;
}

export function InputArea() {
  const [input, setInput] = useState('');
  const [cameraPhoto, setCameraPhoto] = useState<string | null>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const previousOutfitPhotoRef = useRef<string | null>(null);
  const [pendingCall, setPendingCall] = useState<{ stage: 'contact' | 'number' | 'choose' | 'confirm'; contacts: ShivamContact[]; selected?: ShivamContact } | null>(null);
  const [pendingMessage, setPendingMessage] = useState<{
    channel: 'whatsapp' | 'sms';
    stage: 'number' | 'choose' | 'recipient-confirm' | 'message' | 'final-confirm';
    contacts: ShivamContact[];
    selected?: ShivamContact;
    message?: string;
  } | null>(null);

  useEffect(() => {
    const insertScreenText = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (typeof text === 'string' && text.trim()) {
        setInput((current) => current ? current + '\n\n' + text.trim() : text.trim());
        toast.success('स्क्रीनवरील मजकूर चॅटमध्ये आणला.');
      }
    };
    window.addEventListener('shivamInsertScreenText', insertScreenText);
    return () => window.removeEventListener('shivamInsertScreenText', insertScreenText);
  }, []);
  const sendVoiceCommandRef = useRef<(command: string) => void>(() => {});
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wakeRecordingRef = useRef(false);
  const wakeTimerRef = useRef<number | null>(null);
  const wakeAckFallbackRef = useRef<number | null>(null);


  const activeId = useAppStore((s) => s.activeId);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const streamState = useAppStore((s) => s.streamState);
  const messages = useAppStore((s) => s.messages);
  const speechEnabled = useAppStore((s) => s.settings.speechEnabled);
  const maxTokens = useAppStore((s) => s.settings.maxTokens);
  const temperature = useAppStore((s) => s.settings.temperature);
  const createConversation = useAppStore((s) => s.createConversation);
  const addMessage = useAppStore((s) => s.addMessage);
  const updateLastAssistant = useAppStore((s) => s.updateLastAssistant);
  const setStreamState = useAppStore((s) => s.setStreamState);
  const resetStream = useAppStore((s) => s.resetStream);
  const modelLoading = useAppStore((s) => s.modelLoading);
  const deepResearch = useAppStore((s) => s.deepResearch);
  const setDeepResearch = useAppStore((s) => s.setDeepResearch);
  const corpusSync = useResearchCorpusSync(deepResearch);
  const isCurrentChatStreaming = streamState.isStreaming && streamState.conversationId === activeId;

  const {
    state: speechState,
    error: speechError,
    available: speechAvailable,
    startRecording,
    stopRecording,
  } = useSpeech();

  // Abort in-flight stream when the user switches models mid-generation.
  // This prevents errors from trying to continue a stream with a stale model.
  const prevModelRef = useRef(selectedModel);
  useEffect(() => {
    if (prevModelRef.current !== selectedModel && streamState.isStreaming) {
      abortRef.current?.abort();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      resetStream();
      abortRef.current = null;
    }
    prevModelRef.current = selectedModel;
  }, [selectedModel, streamState.isStreaming, resetStream]);

  const micDisabled = !speechEnabled || !speechAvailable || streamState.isStreaming;
  const micReason: 'not-enabled' | 'no-backend' | 'streaming' | undefined =
    !speechEnabled ? 'not-enabled'
    : !speechAvailable ? 'no-backend'
    : streamState.isStreaming ? 'streaming'
    : undefined;

  useEffect(() => {
    if (speechError) {
      toast.error(speechError, { duration: 8000 });
    }
  }, [speechError]);

  // Keep the home-screen hologram in sync with manual microphone use too,
  // not only the always-on wake-word service.
  useEffect(() => {
    if (speechState === 'recording') announceWakeStatus('capturing');
    else if (speechState === 'transcribing') announceWakeStatus('thinking');
  }, [speechState]);


  // Android foreground microphone service keeps wake-word detection active
  // with screen locked; Android shows an ongoing microphone notification.
  useEffect(() => {
    let mounted = true;
    let wakeTimer: number | null = null;
    let wakeStartTimer: number | null = null;
    let captureStarted = false;
    let wakeInProgress = false;
    let wakeCapture: (() => void) | null = null;
    const handleWake = async () => {
      if (!mounted || wakeInProgress) return;
      wakeInProgress = true;
      announceWakeStatus('capturing');
      // Each wake-word event starts a fresh capture cycle. Without resetting
      // this flag, only the first "Shivam" event is accepted after mount.
      captureStarted = false;
      localStorage.removeItem('shivam-wake-pending');
      toast.info('जी, सांगा. काय मदत करू?', { duration: 3500 });
      const capture = async () => {
        if (!mounted || captureStarted) return;
        captureStarted = true;
        try {
          await startRecording();
          wakeTimer = window.setTimeout(async () => {
            let capturedCommand = '';
            try {
              capturedCommand = await stopRecording();
              const command = capturedCommand;
              if (command) {
                setInput(command);
                // A wake-word interaction is an explicit hands-free request:
                // enable spoken replies and submit the captured command.
                useAppStore.getState().updateSettings({ voiceOutputEnabled: true, voiceAutoplay: true });
                announceWakeStatus('thinking');
                toast.success('तुमचा प्रश्न समजला. SHIVAM उत्तर देत आहे.');
                window.setTimeout(() => sendVoiceCommandRef.current(command), 250);
              }
            } catch { toast.error('आवाज समजला नाही. पुन्हा “Shivam” म्हणा.'); }
            captureStarted = false;
            wakeInProgress = false;
            if (!capturedCommand) void startWakeWordListening();
          }, 7000);
        } catch {
          captureStarted = false;
          wakeInProgress = false;
          toast.error('मायक्रोफोन सुरू झाला नाही. परवानगी तपासा.');
          void startWakeWordListening();
        }
      };
      wakeCapture = () => { void capture(); };
      // Use SHIVAM's configured Marathi neural voice for the wake acknowledgement.
      // The fallback timer keeps command capture available if TTS is offline.
      void useTtsStore.getState().speak('shivam-wake-ack', 'जी, सांगा. काय मदत करू?');
      // Avoid opening the microphone over a delayed acknowledgement audio.
      // TTS completion normally starts capture; this is only a last-resort timeout.
      if (wakeAckFallbackRef.current !== null) window.clearTimeout(wakeAckFallbackRef.current);
      wakeAckFallbackRef.current = window.setTimeout(() => {
        wakeAckFallbackRef.current = null;
        if (!captureStarted && wakeInProgress) void capture();
      }, 12000);
    };
    const handleTtsFinished = () => {
      if (wakeAckFallbackRef.current !== null) {
        window.clearTimeout(wakeAckFallbackRef.current);
        wakeAckFallbackRef.current = null;
      }
      if (!mounted || !speechEnabled) {
        announceWakeStatus('off');
        return;
      }
      if (wakeInProgress && wakeCapture) {
        const capture = wakeCapture;
        wakeCapture = null;
        capture();
        return;
      }
      void startWakeWordListening();
    };
    window.addEventListener('shivamTtsFinished', handleTtsFinished);
    window.addEventListener('shivamWakeWord', handleWake);
    if (localStorage.getItem('shivam-wake-pending') === '1') {
      localStorage.removeItem('shivam-wake-pending');
      window.setTimeout(() => { void handleWake(); }, 500);
    }
    if (speechEnabled) {
      // Give a cold-start wake event time to begin command capture before restarting the listener.
      wakeStartTimer = window.setTimeout(() => {
        if (mounted && !captureStarted && !wakeInProgress) void startWakeWordListening();
      }, 4500);
    } else {
      void stopWakeWordListening();
    }
    return () => {
      mounted = false;
      window.removeEventListener('shivamTtsFinished', handleTtsFinished);
      window.removeEventListener('shivamWakeWord', handleWake);
      if (wakeTimer !== null) window.clearTimeout(wakeTimer);
      if (wakeStartTimer !== null) window.clearTimeout(wakeStartTimer);
      if (wakeAckFallbackRef.current !== null) {
        window.clearTimeout(wakeAckFallbackRef.current);
        wakeAckFallbackRef.current = null;
      }
    };
  }, [speechEnabled, startRecording, stopRecording]);

  const handleMicClick = useCallback(async () => {
    if (speechState === 'recording' || speechState === 'transcribing') {
      try {
        const text = await stopRecording();
        if (text) {
          setInput((prev) => (prev ? prev + ' ' + text : text));
        }
      } catch {
        // Error is captured in useSpeech
      } finally {
        if (speechEnabled) {
          void startWakeWordListening();
        }
      }
    } else {
      // Avoid two Android SpeechRecognizer instances competing for the mic.
      await stopWakeWordListening();
      await startRecording();
    }
  }, [speechState, speechEnabled, startRecording, stopRecording]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [input]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    resetStream();
  }, [resetStream]);

  const sendMessage = useCallback(async (voiceCommand?: string) => {
    const content = (voiceCommand ?? input).trim();
    if (!content || streamState.isStreaming) return;

    const normalized = content.toLocaleLowerCase('mr-IN').replace(/[!?.,]/g, ' ').replace(/[ ]+/g, ' ').trim();
    const affirmative = /^(हो|होय|कर|करा|लाव|लावा|पाठव|पाठवा|send|yes|yeah|ok|okay|haan|ha|kar|kara|bhej|bhejo)(\s+(कर|करा|लाव|लावा|पाठव|पाठवा|send))?$/.test(normalized);
    const negative = /^(नाही|नको|रद्द|थांब|no|nope|cancel|nako|nahi)$/.test(normalized);
    const digitText = content.replace(/[०-९]/g, (digit) => String('०१२३४५६७८९'.indexOf(digit)));
    const spokenNumber = digitText.replace(/[^0-9]/g, '');
    const isPhoneNumber = spokenNumber.length >= 7 && spokenNumber.length <= 15;
    const speakCallReply = (reply: string) => {
      let id = activeId;
      if (!id) id = createConversation(selectedModel || 'default');
      addMessage(id, { id: generateId(), role: 'user', content, timestamp: Date.now() });
      const assistantId = generateId();
      addMessage(id, { id: assistantId, role: 'assistant', content: reply, timestamp: Date.now() });
      void useTtsStore.getState().speak(assistantId, reply);
      setInput('');
    };

    if (/^(कॅमेरा|camera)( उघड| सुरू कर| चालू कर| open| open kar| chalu kar| suru kar| ughad)?$/.test(normalized) || /^(फोटो काढ|photo ghe|photo kadh)$/.test(normalized)) {
      cameraInputRef.current?.click();
      speakCallReply('कॅमेरा उघडत आहे. फोटो काढून झाल्यावर मी कपड्यांचा लूक तपासेन.');
      return;
    }

    if (pendingCall) {
      if (negative) {
        setPendingCall(null);
        speakCallReply('ठीक आहे. मी कॉल करत नाही.');
        return;
      }
      if (pendingCall.stage === 'number') {
        if (isPhoneNumber) {
          const selected = { name: 'या नंबरवर', number: spokenNumber };
          setPendingCall({ stage: 'confirm', contacts: [], selected });
          speakCallReply(`शिवम विचारतोय, ${spokenNumber} या नंबरवर कॉल करू का?`);
          return;
        }
        try {
          const result = await findShivamContacts(content);
          if (result.contacts.length === 1) {
            const selected = result.contacts[0];
            setPendingCall({ stage: 'confirm', contacts: result.contacts, selected });
            speakCallReply(`शिवम विचारतोय, मी ${selected.name} यांना कॉल करू का?`);
          } else if (result.contacts.length > 1) {
            setPendingCall({ stage: 'choose', contacts: result.contacts });
            speakCallReply('या नावाचे अनेक संपर्क आहेत. पूर्ण नाव सांगा.');
          } else {
            speakCallReply('संपर्क सापडला नाही. कृपया नाव किंवा मोबाईल नंबर सांगा.');
          }
        } catch (error) {
          speakCallReply(error instanceof Error ? error.message : 'संपर्क शोधता आले नाहीत.');
        }
        return;
      }
      if (pendingCall.stage === 'confirm') {
        if (!affirmative) {
          speakCallReply('कॉल करायचा असल्यास हो म्हणा, किंवा रद्द करण्यासाठी नको म्हणा.');
          return;
        }
        const selected = pendingCall.selected;
        if (!selected) {
          setPendingCall({ stage: 'contact', contacts: [] });
          speakCallReply('शिवम विचारतोय, कोणाला कॉल करू? संपर्काचे नाव सांगा.');
          return;
        }
        setPendingCall(null);
        try {
          await placeShivamCall(selected.number);
          speakCallReply(selected.name === 'या नंबरवर' ? `हो, शिवम आता ${selected.number} या नंबरवर कॉल लावत आहे.` : `हो, शिवम आता ${selected.name} यांना कॉल लावत आहे.`);
        } catch (error) {
          speakCallReply(error instanceof Error ? error.message : 'कॉल करता आला नाही. Android फोन परवानगी तपासा.');
        }
        return;
      }
      if (pendingCall.stage === 'choose') {
        const matches = pendingCall.contacts.filter((contact) =>
          contact.name.toLocaleLowerCase('mr-IN').includes(normalized)
          || contact.number.replace(/\D/g, '').endsWith(normalized.replace(/\D/g, '')),
        );
        if (matches.length !== 1) {
          speakCallReply(matches.length > 1
            ? 'या नावाचे अनेक संपर्क आहेत. पूर्ण नाव किंवा क्रमांकाचा शेवट सांगा.'
            : 'यापैकी कोणता संपर्क आहे ते नावाने सांगा.');
          return;
        }
        const selected = matches[0];
        setPendingCall({ stage: 'confirm', contacts: pendingCall.contacts, selected });
        speakCallReply(selected.name === 'या नंबरवर' ? `शिवम विचारतोय, ${selected.number} या नंबरवर कॉल करू का?` : `शिवम विचारतोय, मी ${selected.name} यांना कॉल करू का?`);
        return;
      }
      try {
        const result = await findShivamContacts(content);
        if (!result.contacts.length) {
          speakCallReply(`${content} या नावाचा संपर्क सापडला नाही. पुन्हा नाव सांगा.`);
          return;
        }
        if (result.contacts.length === 1) {
          const selected = result.contacts[0];
          setPendingCall({ stage: 'confirm', contacts: result.contacts, selected });
          speakCallReply(`शिवम विचारतोय, मी ${selected.name} यांना कॉल करू का?`);
        } else {
          setPendingCall({ stage: 'choose', contacts: result.contacts });
          speakCallReply('या नावाशी जुळणारे अनेक संपर्क आहेत. शिवम विचारतोय, कोणाला कॉल करू?');
        }
      } catch (error) {
        speakCallReply(error instanceof Error ? error.message : 'संपर्क शोधता आले नाहीत. संपर्क परवानगी तपासा.');
      }
      return;
    }

    // Voice-first WhatsApp/SMS flow. SMS is sent natively after the explicit
    // final voice confirmation; WhatsApp uses its official user-visible composer.
    if (pendingMessage) {
      if (negative) {
        setPendingMessage(null);
        speakCallReply('ठीक आहे. मी मेसेज पाठवत नाही.');
        return;
      }
      if (pendingMessage.stage === 'number') {
        if (isPhoneNumber) {
          const selected = { name: 'या नंबरवर', number: spokenNumber };
          setPendingMessage({ ...pendingMessage, stage: 'recipient-confirm', selected });
          speakCallReply(`शिवम विचारतोय, ${spokenNumber} या नंबरवर ${pendingMessage.channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू का?`);
          return;
        }
        try {
          const result = await findShivamContacts(content);
          if (result.contacts.length === 1) {
            const selected = result.contacts[0];
            setPendingMessage({ ...pendingMessage, stage: 'recipient-confirm', contacts: result.contacts, selected });
            speakCallReply(`शिवम विचारतोय, ${selected.name} यांना ${pendingMessage.channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू का?`);
          } else if (result.contacts.length > 1) {
            setPendingMessage({ ...pendingMessage, stage: 'choose', contacts: result.contacts });
            speakCallReply('या नावाचे अनेक संपर्क आहेत. पूर्ण नाव सांगा.');
          } else {
            speakCallReply('संपर्क सापडला नाही. कृपया नाव किंवा मोबाईल नंबर सांगा.');
          }
        } catch (error) {
          speakCallReply(error instanceof Error ? error.message : 'संपर्क शोधता आले नाहीत.');
        }
        return;
      }
      if (pendingMessage.stage === 'choose') {
        const matches = pendingMessage.contacts.filter((contact) =>
          contact.name.toLocaleLowerCase('mr-IN').includes(normalized)
          || contact.number.replace(/\D/g, '').endsWith(normalized.replace(/\D/g, '')),
        );
        if (matches.length !== 1) {
          speakCallReply(matches.length > 1 ? 'या नावाचे अनेक संपर्क आहेत. पूर्ण नाव किंवा क्रमांकाचा शेवट सांगा.' : 'कृपया संपर्काचे पूर्ण नाव सांगा.');
          return;
        }
        const selected = matches[0];
        setPendingMessage({ ...pendingMessage, stage: 'recipient-confirm', selected });
        speakCallReply(`शिवम विचारतोय, ${selected.name} यांना ${pendingMessage.channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू का?`);
        return;
      }
      if (pendingMessage.stage === 'recipient-confirm') {
        if (!affirmative) {
          speakCallReply('पुढे जायचे असल्यास हो म्हणा, किंवा रद्द करण्यासाठी नको म्हणा.');
          return;
        }
        setPendingMessage({ ...pendingMessage, stage: 'message' });
        speakCallReply('शिवम विचारतोय, काय मेसेज पाठवू?');
        return;
      }
      if (pendingMessage.stage === 'message') {
        setPendingMessage({ ...pendingMessage, stage: 'final-confirm', message: content });
        speakCallReply(`शिवम विचारतोय, हा मेसेज पाठवू का? ${content}`);
        return;
      }
      if (pendingMessage.stage === 'final-confirm') {
        if (!affirmative) {
          speakCallReply('मेसेज पाठवण्यासाठी हो म्हणा, किंवा बदलायचा असल्यास नवीन मेसेज सांगा.');
          return;
        }
        const selected = pendingMessage.selected;
        const message = pendingMessage.message;
        const channel = pendingMessage.channel;
        if (!selected || !message) {
          setPendingMessage(null);
          speakCallReply('मेसेजची माहिती अपूर्ण आहे. पुन्हा प्रयत्न करा.');
          return;
        }
        setPendingMessage(null);
        try {
          if (channel === 'sms') {
            const result = await sendShivamSms(selected.number, message);
            speakCallReply(result.message || 'SMS पाठवण्याची विनंती मोबाईल नेटवर्ककडे दिली आहे.');
          } else {
            await openShivamMessageComposer(channel, selected.number, message);
            speakCallReply('WhatsApp उघडले आहे आणि मेसेज तयार केला आहे. पाठवण्यासाठी WhatsApp मधील Send बटण दाबा.');
          }
        } catch (error) {
          speakCallReply(error instanceof Error ? error.message : 'मेसेज अॅप उघडता आले नाही.');
        }
        return;
      }
    }

    const watchmanStartIntent = /(smart watchman|स्मार्ट वॉचमन|वॉचमन|watchman|निगराणी|फोनवर लक्ष ठेव|फोनची काळजी घे)/.test(normalized)
      && /(सुरू|चालू|start|on|लक्ष ठेव|कर|करा|सुरु|suru|chalu)/.test(normalized);
    const watchmanStopIntent = /(smart watchman|स्मार्ट वॉचमन|वॉचमन|watchman|निगराणी)/.test(normalized)
      && /(बंद|थांब|stop|off|band|thamb)/.test(normalized);
    if (watchmanStartIntent || watchmanStopIntent) {
      try {
        if (watchmanStopIntent) {
          await ShivamNavigation.stopWatchman();
          speakCallReply('Smart Watchman बंद करण्याची विनंती केली आहे.');
        } else {
          await ShivamNavigation.startWatchman();
          speakCallReply('Smart Watchman सुरू केला आहे. फोनची बॅटरी, तापमान, स्टोरेज आणि इंटरनेटची स्थिती पार्श्वभूमीत पाहत राहीन. सूचना दिसण्यासाठी Notification परवानगी सुरू ठेवा.');
        }
      } catch (error) {
        speakCallReply(error instanceof Error ? error.message : 'Smart Watchman सुरू किंवा बंद करता आला नाही.');
      }
      return;
    }

    const navigationIntent = /(कुठे जाय|कसा जाय|कशी जाय|कसे जाय|कसा जाऊ|कशी जाऊ|किती दूर|किती अंतर|किती वेळ|रस्ता दाखव|मार्ग दाखव|नेव्हिगेशन|navigation|navigate|directions|route|location|लोकेशन|जायचं आहे|जायचे आहे|ला जायचं|ला जायचे|रस्ता सांग|दिशा सांग|kuthe jay|kasa jay|kashi jay|kase jay|kasa jau|kiti dur|kiti antar|kiti vel|rasta dakhav|marg dakhav|kuthe jaycha|kasa jaycha|kashi jaychi|jaycha aahe|jayche aahe|location sang)/.test(normalized)
      && !/(youtube|यूट्यूब)/.test(normalized);
    if (navigationIntent) {
      const mode: 'driving' | 'bicycling' | 'walking' =
        /(पायी|चालत|walking|walk)/.test(normalized) ? 'walking'
        : /(बाइक|बाईक|दुचाकी|bike|bicycle|cycling)/.test(normalized) ? 'bicycling' : 'driving';
      const destination = normalized
        .replace(/(शिवम|shivam|मला|जरा|कृपया|please|location|लोकेशन|ठिकाण|ठिकाणी|कुठे|कसा|कशी|कसे|जायचं|जायचे|जायचा|जाऊ|जाय|आहे|आहेत|किती|दूर|अंतर|वेळ|लागेल|रस्ता|मार्ग|दाखव|सांग|दिशा|नेव्हिगेशन|navigation|navigate|directions|route|traffic|ट्रॅफिक|गाडीने|कारने|कार|car|driving|drive|पायी|चालत|walking|walk|बाइक|बाईक|दुचाकी|bike|bicycle|cycling|ला|पर्यंत|kasa|kashi|kase|kuthe|jaycha|jaychi|jayche|jau|aahe|ahe|kiti|dur|antar|vel|lagel|rasta|marg|dakhav|sang|paryant|la|paryant|mala|jaraa)/g, ' ')
        .replace(/[!?.,]/g, ' ').replace(/\s+/g, ' ').trim();
      if (destination.length < 2) {
        speakCallReply('शिवम विचारतोय, कुठे जायचे आहे? ठिकाणाचे नाव सांगा.');
        return;
      }
      try {
        await ShivamNavigation.openNavigation({ destination, mode });
        const modeLabel = mode === 'walking' ? 'पायी' : mode === 'bicycling' ? 'बाइकने' : 'गाडीने';
        speakCallReply(`${destination} साठी ${modeLabel} मार्ग Google Maps मध्ये उघडत आहे. तिथे अंतर, अंदाजे वेळ, दिशा आणि उपलब्ध Live Traffic पाहता येईल.`);
      } catch (error) {
        speakCallReply(error instanceof Error ? error.message : 'Navigation सुरू करता आले नाही. Location आणि Google Maps तपासा.');
      }
      return;
    }

    const youtubeIntent = /(youtube|यूट्यूब|यु ट्यूब)/.test(normalized)
      && /(गाणं|गाणे|गाना|गीत|song|video|व्हिडिओ|विडिओ|लाव|लावा|चालू|play|प्ले|सुरू|बघ|दाखव)/.test(normalized);
    if (youtubeIntent) {
      const query = normalized
        .replace(/(youtube|यूट्यूब|यु ट्यूब|ला|वर|हे|हा|ही|ते|तो|गाणं|गाणे|गाना|गीत|song|video|व्हिडिओ|विडिओ|लाव|लावा|चालू|कर|करा|play|प्ले|सुरू|बघ|दाखव|मला|जरा|शिवम|shivam|please|now)/g, ' ')
        .replace(/[ ]+/g, ' ').trim();
      if (query.length < 2) {
        speakCallReply('शिवम विचारतोय, कोणते गाणे किंवा व्हिडिओ लावू? नाव सांगा.');
        return;
      }
      try {
        await searchShivamYouTube(query);
        speakCallReply(`YouTube वर ${query} शोधले आहे. आवडता व्हिडिओ निवडा.`);
      } catch (error) {
        speakCallReply(error instanceof Error ? error.message : 'YouTube उघडता आले नाही.');
      }
      return;
    }

    const whatsappIntent = /(whatsapp|व्हॉट्स ?अॅप|वॉट्स ?अॅप|व्हाट्स ?अॅप|वाट्स ?अॅप)/.test(normalized);
    const smsIntent = /(sms|एसएमएस|text message|टेक्स्ट मेसेज|मजकूर संदेश)/.test(normalized);
    const messageIntent = whatsappIntent || smsIntent;
    if (messageIntent) {
      const channel: 'whatsapp' | 'sms' = whatsappIntent ? 'whatsapp' : 'sms';
      if (isPhoneNumber) {
        const selected = { name: 'या नंबरवर', number: spokenNumber };
        setPendingMessage({ channel, stage: 'recipient-confirm', contacts: [], selected });
        speakCallReply(`शिवम विचारतोय, ${spokenNumber} या नंबरवर ${channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू का?`);
        return;
      }
      const target = normalized
        .replace(/(मला|जरा|शिवम|shivam|whatsapp|व्हॉट्स ?अॅप|वॉट्स ?अॅप|व्हाट्स ?अॅप|वाट्स ?अॅप|sms|एसएमएस|text|message|मेसेज|संदेश|पाठव|पाठवा|कर|करा|please|now)/g, ' ')
        .replace(/(^|[ ])(ला|या|यांना|याला|त्याला|तिला|नंबरवर|नंबर|number|वर|var)(?=[ ]|$)/g, ' ').replace(/ला$/g, '')
        .replace(/[ ]+/g, ' ').trim();
      if (!target) {
        setPendingMessage({ channel, stage: 'number', contacts: [] });
        speakCallReply(`शिवम विचारतोय, कोणाला ${channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू? संपर्काचे नाव किंवा नंबर सांगा.`);
        return;
      }
      try {
        const result = await findShivamContacts(target);
        if (!result.contacts.length) {
          setPendingMessage({ channel, stage: 'number', contacts: [] });
          speakCallReply(`${target} या नावाचा संपर्क सापडला नाही. कृपया मोबाईल नंबर सांगा.`);
        } else if (result.contacts.length === 1) {
          const selected = result.contacts[0];
          setPendingMessage({ channel, stage: 'recipient-confirm', contacts: result.contacts, selected });
          speakCallReply(`शिवम विचारतोय, ${selected.name} यांना ${channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} मेसेज पाठवू का?`);
        } else {
          setPendingMessage({ channel, stage: 'choose', contacts: result.contacts });
          speakCallReply('या नावाशी जुळणारे अनेक संपर्क आहेत. कोणता संपर्क निवडायचा ते नाव सांगा.');
        }
      } catch (error) {
        speakCallReply(error instanceof Error ? error.message : 'संपर्क शोधता आले नाहीत. संपर्क परवानगी तपासा.');
      }
      return;
    }

    const callIntent = /(कॉल|फोन|call|phone)/.test(normalized)
      && /(कर|करा|लाव|लावा|lav|kar|call|phone)/.test(normalized);
    if (callIntent) {
      if (isPhoneNumber) {
        const selected = { name: 'या नंबरवर', number: spokenNumber };
        setPendingCall({ stage: 'confirm', contacts: [], selected });
        speakCallReply(`शिवम विचारतोय, ${spokenNumber} या नंबरवर कॉल करू का?`);
        return;
      }
      const target = normalized
        .replace(/(मला|जरा|शिवम|shivam|त्याला|तिला|याला|हिला|त्यांना|यांना|फोन|कॉल|call|phone|लाव|लावा|कर|करा|lav|kara|kar|please|now)/g, ' ')
        .replace(/(^|\s)(ला|la|या|नंबरवर|नंबर|number|var)(?=\s|$)/g, ' ')
        .replace(/[ ]+/g, ' ').trim();
      setPendingCall({ stage: 'contact', contacts: [] });
      if (!target) {
        setPendingCall({ stage: 'number', contacts: [] });
        speakCallReply('शिवम विचारतोय, कोणाला कॉल करू? संपर्काचे नाव किंवा नंबर सांगा.');
      } else {
        try {
          const result = await findShivamContacts(target);
          if (!result.contacts.length) {
            speakCallReply(`${target} या नावाचा संपर्क सापडला नाही. शिवम विचारतोय, कोणाला कॉल करू?`);
          } else if (result.contacts.length === 1) {
            const selected = result.contacts[0];
            setPendingCall({ stage: 'confirm', contacts: result.contacts, selected });
            speakCallReply(`शिवम विचारतोय, मी ${selected.name} यांना कॉल करू का?`);
          } else {
            setPendingCall({ stage: 'choose', contacts: result.contacts });
            speakCallReply(`${target} नावाचे अनेक संपर्क आहेत. शिवम विचारतोय, कोणाला कॉल करू?`);
          }
        } catch (error) {
          speakCallReply(error instanceof Error ? error.message : 'संपर्क शोधता आले नाहीत. संपर्क परवानगी तपासा.');
        }
      }
      return;
    }
    if (!selectedModel) {
      toast.error('Pick a model first (⌘K)');
      return;
    }

    setInput('');

    let convId = activeId;
    if (!convId) {
      convId = createConversation(selectedModel);
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: cameraPhoto ? (content || 'माझ्या कपड्यांचा लूक तपासून सांगा.') : content,
      timestamp: Date.now(),
    };
    addMessage(convId, userMsg);

    // Build API messages before adding assistant placeholder
    const currentMessages = useAppStore.getState().messages;
    const apiMessages: Array<{ role: string; content: string | Array<Record<string, unknown>> }> = currentMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    if (cameraPhoto) {
      const previousPhoto = previousOutfitPhotoRef.current;
      const photoPrompt = previousPhoto
        ? 'या दोन फोटोंमध्ये पहिला जुना लूक आणि दुसरा नवीन लूक आहे. कपडे बदलल्यानंतर नवीन लूक अधिक शोभतो का ते तुलना करून सांगा. रंगसंगती, फिटिंग, प्रसंगानुरूपता आणि एकूण दिसणे यावर प्रामाणिक पण सभ्य मराठीत मत द्या. चेहरा किंवा व्यक्तीची ओळख याबद्दल कोणताही बदल सुचवू नका.'
        : 'या फोटोतील कपड्यांचा लूक तपासा. रंगसंगती, फिटिंग, प्रसंगानुरूपता आणि एकूण दिसणे यावर प्रामाणिक पण सभ्य मराठीत मत द्या. काय चांगले दिसते आणि काय बदलल्यास अधिक शोभेल ते सांगा. चेहरा किंवा व्यक्तीची ओळख यांचे विश्लेषण किंवा बदल करू नका.';
      const parts: Array<Record<string, unknown>> = [{ type: 'text', text: (content || photoPrompt) + '\n\n' + photoPrompt }];
      if (previousPhoto) parts.push({ type: 'image_url', image_url: { url: previousPhoto } });
      parts.push({ type: 'image_url', image_url: { url: cameraPhoto } });
      apiMessages[apiMessages.length - 1].content = parts;
      previousOutfitPhotoRef.current = cameraPhoto;
      setCameraPhoto(null);
    }

    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isResearch: deepResearch || undefined,
    };
    addMessage(convId, assistantMsg);

    // Start streaming
    const startTime = Date.now();
    const timer = setInterval(() => {
      setStreamState({ elapsedMs: Date.now() - startTime });
    }, 100);
    timerRef.current = timer;

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedContent = '';
    let lastStreamEvent = 'none';
    let lastStreamData = '';
    let usage: TokenUsage | undefined;
    let complexity: { score: number; tier: string; suggested_max_tokens: number } | undefined;
    let routedEngine: string | undefined;
    const toolCalls: ToolCallInfo[] = [];
    const researchTraces: ResearchSearchTrace[] = [];
    const researchSourcesByRef = new Map<number, ResearchSource>();
    const flushSources = () =>
      Array.from(researchSourcesByRef.values()).sort((a, b) => a.ref - b.ref);
    let lastFlush = 0;
    let ttftMs: number | undefined;

    setStreamState({
      conversationId: convId,
      isStreaming: true,
      phase: deepResearch ? 'Researching...' : 'Generating...',
      elapsedMs: 0,
      activeToolCalls: [],
      content: '',
    });
    useAppStore.getState().addLogEntry({
      timestamp: Date.now(),
      level: 'info',
      category: 'chat',
      message: deepResearch
        ? `Research: "${content.slice(0, 80)}${content.length > 80 ? '...' : ''}"`
        : `Request: "${content.slice(0, 80)}${content.length > 80 ? '...' : ''}" → ${selectedModel}`,
    });

    try {
      if (deepResearch) {
        for await (const ev of streamResearch(
          content,
          selectedModel,
          controller.signal,
        )) {
          if (ev.type === 'search_call') {
            const trace: ResearchSearchTrace = {
              id: generateId(),
              query: ev.arguments?.query ?? '',
              person: ev.arguments?.person,
              timeRange: ev.arguments?.time_range,
              status: 'pending',
            };
            researchTraces.push(trace);
            setStreamState({ phase: `Searching: ${trace.query}` });
            updateLastAssistant(
              convId,
              accumulatedContent,
              undefined,
              undefined,
              undefined,
              undefined,
              [...researchTraces],
              flushSources(),
            );
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(),
              level: 'info',
              category: 'tool',
              message: `Search: "${trace.query}"${trace.person ? ` (person: ${trace.person})` : ''}`,
            });
          } else if (ev.type === 'search_result') {
            const pending = [...researchTraces].reverse().find((t) => t.status === 'pending');
            if (pending) {
              pending.status = 'complete';
              pending.numHits = ev.num_hits;
              pending.topTitles = ev.top_titles;
            }
            if (ev.sources) {
              for (const src of ev.sources) {
                if (src && typeof src.ref === 'number' && !researchSourcesByRef.has(src.ref)) {
                  researchSourcesByRef.set(src.ref, src);
                }
              }
            }
            updateLastAssistant(
              convId,
              accumulatedContent,
              undefined,
              undefined,
              undefined,
              undefined,
              [...researchTraces],
              flushSources(),
            );
          } else if (ev.type === 'synthesis') {
            if (!ttftMs) ttftMs = Date.now() - startTime;
            accumulatedContent += ev.text;
            setStreamState({ content: accumulatedContent, phase: '' });
            const now = Date.now();
            if (now - lastFlush >= 80) {
              updateLastAssistant(
                convId,
                accumulatedContent,
                undefined,
                undefined,
                undefined,
                undefined,
                [...researchTraces],
                flushSources(),
              );
              lastFlush = now;
            }
          } else if (ev.type === 'system_metrics') {
            // Live GPU sample — feed straight to the System panel so Power
            // (W) and Energy (kJ) tick up in real time as the agent runs.
            useAppStore.getState().setLiveEnergy({
              power_w: ev.power_w,
              energy_j: ev.energy_j,
              duration_s: ev.duration_s,
            });
          } else if (ev.type === 'error') {
            // Backend setup/worker failure (Ollama down, planner model
            // missing, KnowledgeStore locked, etc.). Without surfacing the
            // message, the user sees only the generic "No response was
            // generated" fallback and has no way to self-diagnose.
            const msg = ev.message || 'Research failed (no detail provided)';
            accumulatedContent = accumulatedContent
              ? `${accumulatedContent}

**Research stopped:** ${msg}`
              : `**Research failed:** ${msg}`;
            setStreamState({ content: accumulatedContent, phase: '' });
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(),
              level: 'error',
              category: 'chat',
              message: `Deep Research error: ${msg}`,
            });
            toast.error(msg, { duration: 8000 });
          } else if (ev.type === 'done') {
            if (ev.usage) {
              usage = {
                prompt_tokens: ev.usage.prompt_tokens ?? 0,
                completion_tokens: ev.usage.completion_tokens ?? 0,
                total_tokens:
                  ev.usage.total_tokens ??
                  (ev.usage.prompt_tokens ?? 0) +
                    (ev.usage.completion_tokens ?? 0),
              };
              // Optimistically roll this research turn into the session
              // counters so the Session panel updates the moment the
              // stream finishes, regardless of how /v1/savings aggregates
              // research telemetry server-side.
              useAppStore.getState().incrementSavings(usage);
            }
            // Hold the final live numbers visible for a beat so the panel
            // doesn't flash to 0 between the SSE close and the next
            // /v1/telemetry/energy poll picking up the persisted record.
            window.setTimeout(() => {
              useAppStore.getState().setLiveEnergy(null);
            }, 1500);
            break;
          }
        }
      } else {
      for await (const sseEvent of streamChat(
        { model: selectedModel, messages: apiMessages, stream: true, temperature, max_tokens: maxTokens },
        controller.signal,
      )) {
        const eventName = sseEvent.event || 'message';
        lastStreamEvent = eventName;
        lastStreamData = (sseEvent.data || '').slice(0, 500);

        if (eventName === 'agent_turn_start') {
          setStreamState({ phase: 'Agent thinking...' });
        } else if (eventName === 'inference_start') {
        setStreamState({ phase: 'Generating...' });
        let modelInfo: { selected_model?: string; actual_model?: string } = {};
        try {
          modelInfo = JSON.parse(sseEvent.data || '{}');
        } catch {}
        const actualModel = modelInfo.actual_model || modelInfo.selected_model || selectedModel;
        useAppStore.getState().addLogEntry({
          timestamp: Date.now(), level: 'info', category: 'chat',
          message: `Generating with ${actualModel}${actualModel !== selectedModel ? ` (selected: ${selectedModel})` : ''}...`,
        });
      } else if (eventName === 'inference_model') {
        try {
          const modelInfo = JSON.parse(sseEvent.data || '{}');
          if (modelInfo.actual_model) {
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(), level: 'info', category: 'chat',
              message: `Actual provider model: ${modelInfo.actual_model}`,
            });
          }
        } catch {}
      } else if (eventName === 'tool_call_start') {
          try {
            const data = JSON.parse(sseEvent.data);
            const tc: ToolCallInfo = {
              id: generateId(),
              tool: data.tool,
              arguments: serializeToolCallArguments(data.arguments),
              status: 'running',
            };
            toolCalls.push(tc);
            setStreamState({
              phase: `Calling ${data.tool}...`,
              activeToolCalls: [...toolCalls],
            });
            updateLastAssistant(convId, accumulatedContent, [...toolCalls]);
            useAppStore.getState().addLogEntry({
              timestamp: Date.now(), level: 'info', category: 'tool',
              message: `Calling ${data.tool}(${serializeToolCallArguments(data.arguments)})`,
            });
          } catch {}
        } else if (eventName === 'tool_call_end') {
          try {
            const data = JSON.parse(sseEvent.data);
            const tc = toolCalls.find(
              (t) => t.tool === data.tool && t.status === 'running',
            );
            if (tc) {
              tc.status = data.success ? 'success' : 'error';
              tc.latency = data.latency;
              tc.result = data.result;
            }
            if (data.tool === 'create_document_file' && data.success && data.result?.download_url) {
              const fileName = String(data.result.filename || 'तयार केलेली फाइल');
              const downloadUrl = String(data.result.download_url);
              if (downloadUrl.startsWith('/v1/documents/download/')) {
                void apiFetch(downloadUrl).then(async (response) => {
                  if (!response.ok) throw new Error('फाइल डाउनलोड करता आली नाही.');
                  const fileBlob = await response.blob();
                  const objectUrl = URL.createObjectURL(fileBlob);
                  accumulatedContent += '\n\n[' + fileName + ' डाउनलोड करा](' + objectUrl + ')';
                  updateLastAssistant(convId, accumulatedContent, [...toolCalls]);
                }).catch(() => {
                  toast.error('फाइल तयार झाली; पण डाउनलोड लिंक उघडता आली नाही. पुन्हा प्रयत्न करा.');
                });
              }
            }
            setStreamState({
              phase: 'Generating...',
              activeToolCalls: [...toolCalls],
            });
            updateLastAssistant(convId, accumulatedContent, [...toolCalls]);
          } catch {}
        } else {
          try {
            const data = JSON.parse(sseEvent.data);
            const delta = data.choices?.[0]?.delta;
            if (data.usage) usage = data.usage;
            if (data.complexity) complexity = data.complexity;
            routedEngine = engineFromCompletionChunk(data) ?? routedEngine;
            if (delta?.content) {
              if (!ttftMs) ttftMs = Date.now() - startTime;
              accumulatedContent += delta.content;
              setStreamState({ content: accumulatedContent, phase: '' });

              const now = Date.now();
              if (now - lastFlush >= 80) {
                updateLastAssistant(
                  convId,
                  accumulatedContent,
                  toolCalls.length > 0 ? [...toolCalls] : undefined,
                );
                lastFlush = now;
              }
            }
            // Wait for [DONE]; providers may send content after finish_reason.
          } catch {}
        }
      }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        // User cancelled or model switch — keep whatever was accumulated
        if (!accumulatedContent) accumulatedContent = '(Generation stopped)';
      } else {
        const errMsg = err?.message || String(err);
        accumulatedContent =
          accumulatedContent || `Error: ${errMsg}`;
        useAppStore.getState().addLogEntry({
          timestamp: Date.now(), level: 'error', category: 'chat',
          message: `Stream error: ${errMsg}`,
        });
      }
      // If we tore out mid-research, make sure the live System panel
      // numbers don't get stuck on the last sample.
      useAppStore.getState().setLiveEnergy(null);
    } finally {
      if (!accumulatedContent) {
        accumulatedContent = `SHIVAM निदान: उत्तराचा मजकूर मिळाला नाही. API: ${getBase()}. निवडलेले मॉडेल: ${selectedModel}. शेवटचा SSE इव्हेंट: ${lastStreamEvent}. डेटा: ${lastStreamData || '(रिकामा)'}`;
        useAppStore.getState().addLogEntry({ timestamp: Date.now(), level: 'error', category: 'chat', message: accumulatedContent });
      }
      const totalMs = Date.now() - startTime;
      const appState = useAppStore.getState();
      const selectedOwner = appState.models.find((m) => m.id === selectedModel)?.owned_by;
      const engineLabel = resolveChatEngine({
        routedEngine,
        serverEngine: appState.serverInfo?.engine,
        selectedModel,
        selectedOwner,
      });
      const telemetry: MessageTelemetry = {
        engine: engineLabel,
        model_id: selectedModel,
        total_ms: totalMs,
        ttft_ms: ttftMs,
        tokens_per_sec: usage?.completion_tokens
          ? usage.completion_tokens / (totalMs / 1000)
          : undefined,
        complexity_score: complexity?.score,
        complexity_tier: complexity?.tier,
        suggested_max_tokens: complexity?.suggested_max_tokens,
      };
      // Check if the response has digest audio available
      let audioMeta: { url: string } | undefined;
      try {
        const digestRes = await fetch(`${getBase()}/api/digest`);
        if (digestRes.ok) {
          const digest = await digestRes.json();
          if (digest.audio_available) {
            audioMeta = { url: `${getBase()}/api/digest/audio` };
          }
        }
      } catch {
        // Not a digest response or server unavailable — skip
      }

      updateLastAssistant(
        convId,
        accumulatedContent,
        toolCalls.length > 0 ? toolCalls : undefined,
        usage,
        telemetry,
        audioMeta,
        researchTraces.length > 0 ? researchTraces : undefined,
        researchSourcesByRef.size > 0 ? flushSources() : undefined,
      );
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      resetStream();
      useAppStore.getState().addLogEntry({
        timestamp: Date.now(), level: 'info', category: 'chat',
        message: `Response: ${accumulatedContent.length} chars`,
      });
      abortRef.current = null;

      // Research path updates session counters optimistically from the
      // `done` event's usage payload — re-fetching here would overwrite
      // it with a potentially stale snapshot if the server's research
      // telemetry hasn't been merged into /v1/savings yet.
      if (!deepResearch) {
        fetchSavings()
          .then((data) => useAppStore.getState().setSavings(data))
          .catch(() => {});
      }
    }
  }, [
    input,
    activeId,
    selectedModel,
    streamState.isStreaming,
    createConversation,
    addMessage,
    updateLastAssistant,
    setStreamState,
    resetStream,
    deepResearch,
    temperature,
    maxTokens,
    pendingCall,
    pendingMessage,
    cameraPhoto,
  ]);

  sendVoiceCommandRef.current = (command: string) => { void sendMessage(command); };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2" style={{ maxWidth: 'var(--chat-max-width)', margin: '0 auto', width: '100%' }}>
      <div className="mb-2 flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setDeepResearch(!deepResearch)}
            disabled={streamState.isStreaming}
            aria-pressed={deepResearch}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-colors cursor-pointer disabled:cursor-default disabled:opacity-50"
            style={{
              background: deepResearch ? 'var(--color-accent-subtle)' : 'transparent',
              border: `1px solid ${deepResearch ? 'var(--color-accent)' : 'var(--color-border)'}`,
              color: deepResearch ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
            }}
            title={deepResearch ? 'Deep Research: on' : 'Deep Research: off'}
          >
            <Search size={12} />
            Deep Research
          </button>
        </div>
        {deepResearch && corpusSync.syncing && corpusSync.itemsSynced > 0 && (
          <div
            className="text-[11px] leading-snug"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Searching over{' '}
            <span key={corpusSync.itemsSynced} className="sync-bump" style={{ color: 'var(--color-text-secondary)' }}>
              {corpusSync.itemsSynced.toLocaleString()}
            </span>{' '}
            items — sync in progress, results will improve as more data is indexed.
          </div>
        )}
      </div>
      {cameraPhoto && (
        <div className="mb-2 flex items-center gap-3 rounded-xl p-2" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
          <img src={cameraPhoto} alt="कपड्यांचा फोटो" className="h-14 w-12 rounded-lg object-cover" />
          <span className="flex-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>फोटो तयार आहे. फोटो समजणारे AI मॉडेल निवडलेले असावे.</span>
          <button type="button" onClick={() => setCameraPhoto(null)} aria-label="फोटो काढून टाका" className="p-2 rounded-lg" style={{ color: 'var(--color-text-tertiary)' }}><X size={16} /></button>
        </div>
      )}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        aria-label="कपड्यांचा फोटो काढा"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = '';
          if (!file) return;
          if (!file.type.startsWith('image/')) { toast.error('कृपया फोटो निवडा.'); return; }
          if (file.size > 12 * 1024 * 1024) { toast.error('फोटो 12 MB पेक्षा लहान असावा.'); return; }
          const reader = new FileReader();
          reader.onload = () => {
            if (typeof reader.result !== 'string') { toast.error('फोटो वाचता आला नाही.'); return; }
            const image = new Image();
            image.onload = () => {
              const scale = Math.min(1, 1280 / Math.max(image.width, image.height));
              const canvas = document.createElement('canvas');
              canvas.width = Math.max(1, Math.round(image.width * scale));
              canvas.height = Math.max(1, Math.round(image.height * scale));
              const context = canvas.getContext('2d');
              if (!context) { toast.error('फोटो तयार करता आला नाही.'); return; }
              context.drawImage(image, 0, 0, canvas.width, canvas.height);
              setCameraPhoto(canvas.toDataURL('image/jpeg', 0.76));
              setInput((current) => current || 'माझ्या कपड्यांचा लूक कसा दिसतो?');
            };
            image.onerror = () => toast.error('फोटो उघडता आला नाही.');
            image.src = reader.result;
          };
          reader.onerror = () => toast.error('फोटो वाचता आला नाही.');
          reader.readAsDataURL(file);
        }}
      />
      <div
        className="flex items-center gap-2 rounded-2xl px-4 py-3 transition-shadow"
        style={{
          background: 'var(--color-input-bg)',
          border: '1px solid var(--color-input-border)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={selectedModel ? 'SHIVAM ला विचारा...' : 'आधी AI मॉडेल निवडा (⌘K)...'}
          rows={1}
          className="flex-1 bg-transparent outline-none resize-none text-sm leading-relaxed"
          style={{ color: 'var(--color-text)', maxHeight: '200px' }}
          disabled={streamState.isStreaming || modelLoading}
        />
        {isCurrentChatStreaming ? (
          <button
            onClick={stopStreaming}
            className="p-2 rounded-xl transition-colors shrink-0 cursor-pointer"
            style={{ background: 'var(--color-error)', color: 'var(--color-on-accent)' }}
            title="Stop generating"
          >
            <Square size={16} />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              disabled={streamState.isStreaming || modelLoading || !selectedModel}
              title="कपड्यांचा फोटो काढा"
              aria-label="कपड्यांचा फोटो काढा"
              className="p-2 rounded-xl transition-colors shrink-0 cursor-pointer disabled:opacity-30"
              style={{ color: 'var(--color-text-secondary)', background: 'var(--color-bg-tertiary)' }}
            >
              <Camera size={17} />
            </button>
            <MicButton
              state={speechState}
              onClick={handleMicClick}
              disabled={micDisabled}
              reason={micReason}
            />
            <button
              onClick={() => { void sendMessage(); }}
              disabled={streamState.isStreaming || !input.trim() || modelLoading || !selectedModel}
              title={selectedModel ? 'संदेश पाठवा' : 'आधी AI मॉडेल निवडा (⌘K)'}
              className="p-2 rounded-xl transition-colors shrink-0 cursor-pointer disabled:opacity-30 disabled:cursor-default"
              style={{
                background: input.trim() ? 'var(--color-accent)' : 'var(--color-bg-tertiary)',
                color: input.trim() ? 'white' : 'var(--color-text-tertiary)',
              }}
            >
              <Send size={16} />
            </button>
          </div>
        )}
      </div>
      <div className="flex items-center justify-center mt-2 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
        <span>
          <kbd className="font-mono">Enter</kbd> पाठवा &middot;{' '}
          <kbd className="font-mono">Shift+Enter</kbd> नवीन ओळ
        </span>
      </div>
    </div>
  );
}
