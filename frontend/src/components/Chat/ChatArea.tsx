import { useRef, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { MessageBubble } from './MessageBubble';
import { InputArea } from './InputArea';
import { StreamingDots } from './StreamingDots';
import { useAppStore } from '../../lib/store';
import { shouldAutoplayFinishedReply, useTtsStore } from '../../lib/tts';
import { stripThinkTags } from '../../lib/message-text';
import { PanelRightOpen, PanelRightClose, Database, MessageSquare, X } from 'lucide-react';
import { listConnectors } from '../../lib/connectors-api';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'शुभ सकाळ';
  if (hour < 18) return 'शुभ दुपार';
  return 'शुभ संध्याकाळ';
}

export function ChatArea() {
  const activeId = useAppStore((s) => s.activeId);
  const messages = useAppStore((s) => s.messages);
  const streamState = useAppStore((s) => s.streamState);
  const systemPanelOpen = useAppStore((s) => s.systemPanelOpen);
  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const shouldAutoScroll = useRef(true);
  const wasStreaming = useRef(false);
  const lastScrollTop = useRef(0);
  const isCurrentChatStreaming = streamState.isStreaming && streamState.conversationId === activeId;

  const [wakeStatus, setWakeStatus] = useState<'listening' | 'capturing' | 'thinking' | 'off'>('off');
  useEffect(() => {
    const handleWakeStatus = (event: Event) => {
      const next = (event as CustomEvent<string>).detail;
      if (next === 'listening' || next === 'capturing' || next === 'thinking' || next === 'off') {
        setWakeStatus(next);
      }
    };
    window.addEventListener('shivamWakeStatus', handleWakeStatus);
    return () => window.removeEventListener('shivamWakeStatus', handleWakeStatus);
  }, []);
  const [batteryLevel, setBatteryLevel] = useState<number | null>(null);
  const [networkOnline, setNetworkOnline] = useState(() => typeof navigator === 'undefined' ? true : navigator.onLine);
  const [networkType, setNetworkType] = useState('—');
  const [hudClock, setHudClock] = useState(() => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
  const ttsPlaybackState = useTtsStore((s) => s.state);
  const weatherCities = [
    { name: 'Badnera', lat: 20.8648, lon: 77.73521 },
    { name: 'Shrirampur', lat: 19.6208, lon: 74.6544 },
    { name: 'Amravati', lat: 20.9374, lon: 77.7796 },
    { name: 'Nagpur', lat: 21.1458, lon: 79.0882 },
    { name: 'Pune', lat: 18.5204, lon: 73.8567 },
    { name: 'Mumbai', lat: 19.076, lon: 72.8777 },
  ];
  const [weatherCity, setWeatherCity] = useState('Badnera');
  const [weatherSummary, setWeatherSummary] = useState('LOADING');
  const [weatherBusy, setWeatherBusy] = useState(false);

  useEffect(() => {
    const city = weatherCities.find((item) => item.name === weatherCity) ?? weatherCities[0];
    let cancelled = false;
    const loadWeather = async () => {
      setWeatherBusy(true);
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${city.lat}&longitude=${city.lon}&current=temperature_2m,relative_humidity_2m,weather_code&timezone=Asia%2FKolkata`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Weather unavailable');
        const data = await response.json() as { current?: { temperature_2m?: number; relative_humidity_2m?: number; weather_code?: number } };
        const current = data.current;
        if (!current || typeof current.temperature_2m !== 'number') throw new Error('Weather data missing');
        const code = current.weather_code ?? -1;
        const condition = code === 0 ? 'CLEAR' : [1, 2, 3].includes(code) ? 'CLOUDY'
          : [45, 48].includes(code) ? 'FOG' : [51, 53, 55, 56, 57].includes(code) ? 'DRIZZLE'
          : [61, 63, 65, 66, 67, 80, 81, 82].includes(code) ? 'RAIN'
          : [71, 73, 75, 77, 85, 86].includes(code) ? 'SNOW'
          : [95, 96, 99].includes(code) ? 'STORM' : 'WEATHER';
        if (!cancelled) setWeatherSummary(`${Math.round(current.temperature_2m)}°C · ${condition}`);
      } catch {
        if (!cancelled) setWeatherSummary('UNAVAILABLE');
      } finally {
        if (!cancelled) setWeatherBusy(false);
      }
    };
    void loadWeather();
    const timer = window.setInterval(loadWeather, 15 * 60 * 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [weatherCity]);

  useEffect(() => {
    type BatteryLike = EventTarget & { level: number; addEventListener: (type: string, listener: EventListener) => void; removeEventListener: (type: string, listener: EventListener) => void };
    type ConnectionLike = EventTarget & { effectiveType?: string; type?: string };
    const nav = navigator as Navigator & {
      getBattery?: () => Promise<BatteryLike>;
      connection?: ConnectionLike;
      mozConnection?: ConnectionLike;
      webkitConnection?: ConnectionLike;
    };
    let battery: BatteryLike | null = null;
    let active = true;
    const updateBattery = () => {
      if (battery) setBatteryLevel(Math.round(battery.level * 100));
    };
    const updateNetwork = () => {
      setNetworkOnline(navigator.onLine);
      const connection = nav.connection ?? nav.mozConnection ?? nav.webkitConnection;
      setNetworkType(connection?.effectiveType ?? connection?.type ?? (navigator.onLine ? 'CONNECTED' : 'OFFLINE'));
    };
    const updateClock = () => setHudClock(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const connection = nav.connection ?? nav.mozConnection ?? nav.webkitConnection;
    window.addEventListener('online', updateNetwork);
    window.addEventListener('offline', updateNetwork);
    connection?.addEventListener('change', updateNetwork);
    updateNetwork();
    updateClock();
    const clockTimer = window.setInterval(updateClock, 30_000);
    nav.getBattery?.().then((value) => {
      if (!active) return;
      battery = value;
      updateBattery();
      battery.addEventListener('levelchange', updateBattery);
    }).catch(() => setBatteryLevel(null));
    return () => {
      active = false;
      window.clearInterval(clockTimer);
      window.removeEventListener('online', updateNetwork);
      window.removeEventListener('offline', updateNetwork);
      connection?.removeEventListener('change', updateNetwork);
      battery?.removeEventListener('levelchange', updateBattery);
    };
  }, []);

  const reactorState = isCurrentChatStreaming ? 'executing'
    : ttsPlaybackState === 'speaking' ? 'speaking'
    : wakeStatus === 'capturing' || wakeStatus === 'listening' ? 'listening'
    : wakeStatus === 'thinking' || ttsPlaybackState === 'loading' ? 'thinking' : 'idle';
  const reactorLabel = reactorState === 'listening' ? 'ऐकत आहे'
    : reactorState === 'thinking' ? 'विचार करत आहे'
    : reactorState === 'speaking' ? 'बोलत आहे'
    : reactorState === 'executing' ? 'काम सुरू आहे' : 'तुमच्या सेवेत';

  // Autoplay: speak a reply once it is finished, never while it streams -- a
  // partial sentence would be synthesized and then cut off by the next chunk.
  // autoSpokenId fences the message so re-renders cannot repeat it.
  const voiceOutputEnabled = useAppStore((s) => s.settings.voiceOutputEnabled);
  const voiceAutoplay = useAppStore((s) => s.settings.voiceAutoplay);
  // Probe the backend as soon as voice output is switched on. Without this the
  // first reply could never autoplay: `available` is only set by ensureHealth,
  // which until now ran solely from the per-message read-aloud button -- and
  // that button does not exist until a reply is already on screen.
  useEffect(() => {
    if (!voiceOutputEnabled) return;
    useTtsStore.getState().ensureHealth();
  }, [voiceOutputEnabled]);

  // Speak on the falling edge of a stream -- the moment a reply finishes -- and
  // never merely because a finished reply happens to be on screen. Opening the
  // app or switching conversations would otherwise read stale history aloud,
  // and browsers block that anyway: playback with no preceding user gesture is
  // rejected outright, so the failure would be silent in both senses.
  const streamingConversationRef = useRef<string | null>(null);
  useEffect(() => {
    const last = messages[messages.length - 1];
    const tts = useTtsStore.getState();
    const justFinished = shouldAutoplayFinishedReply(
      streamingConversationRef.current,
      activeId,
      streamState.isStreaming,
      last,
      tts.autoSpokenId,
    );
    streamingConversationRef.current = isCurrentChatStreaming ? activeId : null;

    if (!justFinished) return;
    if (!voiceOutputEnabled || !voiceAutoplay) return;

    if (!last || last.role !== 'assistant' || activeId === null) return;

    // Model loading may still be in flight when a fast reply completes. Wait
    // for the probe, then confirm that this is still the active finished reply.
    const completedConversationId = activeId;
    const completedMessageId = last.id;
    void tts.ensureHealth().then(() => {
      const app = useAppStore.getState();
      const currentTts = useTtsStore.getState();
      const currentLast = app.messages[app.messages.length - 1];
      if (app.activeId !== completedConversationId || app.streamState.isStreaming) return;
      if (!app.settings.voiceOutputEnabled || !app.settings.voiceAutoplay) return;
      if (currentTts.available !== true) {
        window.dispatchEvent(new Event('shivamTtsFinished'));
        return;
      }
      if (currentLast?.id !== completedMessageId) return;
      if (currentTts.autoSpokenId === completedMessageId) return;

      const text = stripThinkTags(currentLast.content);
      if (!text) return;
      currentTts.markAutoSpoken(completedMessageId);
      void currentTts.speak(completedMessageId, text);
    });
  }, [activeId, messages, streamState.isStreaming, isCurrentChatStreaming, voiceOutputEnabled, voiceAutoplay]);
  const currentStreamContent = isCurrentChatStreaming ? streamState.content : '';

  // Check if any data sources are connected
  const [hasConnectedSources, setHasConnectedSources] = useState<boolean | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    listConnectors()
      .then((list) => setHasConnectedSources(list.some((c) => c.connected)))
      .catch(() => setHasConnectedSources(null));
  }, []);

  useEffect(() => {
    // Sending a message always pins the view to the bottom, even if the
    // user had scrolled up to read earlier messages.
    if (isCurrentChatStreaming && !wasStreaming.current) {
      shouldAutoScroll.current = true;
    }
    wasStreaming.current = isCurrentChatStreaming;
    if (shouldAutoScroll.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, currentStreamContent, isCurrentChatStreaming]);

  const handleScroll = () => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    const distance = scrollHeight - scrollTop - clientHeight;
    const scrolledUp = scrollTop < lastScrollTop.current;
    lastScrollTop.current = scrollTop;
    if (scrolledUp && distance >= 1) {
      // Any upward scroll away from the bottom stops autoscroll immediately,
      // so streaming content never fights the user (no jitter). Sub-1px
      // upward movement (elastic bounce settling at the bottom) is ignored.
      shouldAutoScroll.current = false;
    } else if (!scrolledUp) {
      // Re-engage when scrolled back to the bottom. < 2 rather than < 1:
      // at fractional zoom levels the at-bottom residual can reach 1px,
      // which would otherwise leave autoscroll permanently disengaged.
      shouldAutoScroll.current = distance < 2;
    }
  };

  const isEmpty = messages.length === 0 && !isCurrentChatStreaming;

  const PanelIcon = systemPanelOpen ? PanelRightClose : PanelRightOpen;

  return (
    <div className="flex flex-col h-full">
      {/* Toggle bar */}
      <div className="flex items-center justify-end px-3 py-1.5 shrink-0">
        <button
          onClick={toggleSystemPanel}
          className="p-1.5 rounded-md transition-colors cursor-pointer"
          style={{ color: 'var(--color-text-tertiary)' }}
          title={`${systemPanelOpen ? 'Hide' : 'Show'} system panel (${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+I)`}
        >
          <PanelIcon size={16} />
        </button>
      </div>

      {/* Data sources banner */}
      {hasConnectedSources === false && !bannerDismissed && (
        <div
          className="mx-4 mb-2 flex items-center gap-3 px-4 py-3 rounded-lg text-sm shrink-0"
          style={{
            background: 'var(--color-accent-subtle)',
            border: '1px solid var(--color-border)',
          }}
        >
          <Database size={16} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
          <span style={{ color: 'var(--color-text-secondary)', flex: 1 }}>
            वैयक्तिक उत्तरे मिळवण्यासाठी Gmail, मेसेजिंग आणि इतर डेटा स्रोत जोडा.
          </span>
          <button
            onClick={() => navigate('/data-sources')}
            className="px-3 py-1 rounded text-xs font-medium cursor-pointer"
            style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)', border: 'none' }}
          >
            जोडा
          </button>
          <button
            onClick={() => setBannerDismissed(true)}
            className="p-1 rounded cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)', background: 'transparent', border: 'none' }}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {isEmpty ? (
          <div className={`shivam-home shivam-home-${reactorState} flex flex-col items-center justify-center h-full px-4`} data-reactor-state={reactorState}>
            <div className="shivam-home-meta">
              <span className="hud-heartbeat" /> वैयक्तिक AI प्रणाली
              <span className="shivam-meta-line" />
              <span>SHIVAM·01</span>
            </div>
            <div className="shivam-hud-corner shivam-hud-corner-left" aria-hidden="true"><span>SYS ONLINE</span><b>01 / CORE</b></div>
            <div className="shivam-hud-corner shivam-hud-corner-right" aria-hidden="true"><span>NEURAL LINK</span><b>SECURE</b></div>
            <div className="shivam-reactor" aria-hidden="true">
              <div className="shivam-reactor-ring shivam-ring-outer" />
              <div className="shivam-reactor-ring shivam-ring-mid" />
              <div className="shivam-reactor-ring shivam-ring-inner" />
              <div className="shivam-reactor-cross shivam-cross-a" />
              <div className="shivam-reactor-cross shivam-cross-b" />
              <div className="shivam-reactor-core shivam-avatar-core">
                <div className="shivam-avatar" aria-hidden="true">
                  <span className="shivam-avatar-brow" />
                  <span className="shivam-avatar-eye shivam-avatar-eye-left" />
                  <span className="shivam-avatar-eye shivam-avatar-eye-right" />
                  <span className="shivam-avatar-nose" />
                  <span className="shivam-avatar-mouth" />
                  <span className="shivam-avatar-scan" />
                </div>
              </div>
              <span className="shivam-orbit-dot shivam-dot-a" />
              <span className="shivam-orbit-dot shivam-dot-b" />
              <span className="shivam-orbit-dot shivam-dot-c" />
            </div>
            <div className="shivam-wordmark">SHIVAM</div>
            <div className="shivam-subtitle">कृत्रिम बुद्धिमत्ता</div>
            <div className="shivam-voice-wave" aria-hidden="true">{Array.from({ length: 15 }, (_, i) => <span key={i} style={{ animationDelay: `${i * 55}ms` }} />)}</div>
            <div className="shivam-ready"><span className="hud-heartbeat" /> {reactorLabel} <span>•</span> प्रणाली सज्ज</div>
            <div className="shivam-glass-hud" aria-label="SHIVAM live device telemetry">
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">◈</span><span className="shivam-glass-label">CORE</span><b>ONLINE</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">⌁</span><span className="shivam-glass-label">VOICE</span><b>{reactorState === 'listening' ? 'ACTIVE' : reactorState === 'speaking' ? 'SPEAK' : 'READY'}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">ϟ</span><span className="shivam-glass-label">BATTERY</span><b>{batteryLevel === null ? 'N/A' : `${batteryLevel}%`}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">⌁</span><span className="shivam-glass-label">NETWORK</span><b>{networkOnline ? networkType.toUpperCase() : 'OFFLINE'}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">◷</span><span className="shivam-glass-label">LOCAL TIME</span><b>{hudClock}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">☼</span><span className="shivam-glass-label">WEATHER · {weatherCity.toUpperCase()}</span><b>{weatherBusy && weatherSummary === 'LOADING' ? 'LOADING' : weatherSummary}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">♨</span><span className="shivam-glass-label">CPU TEMP</span><b>N/A</b></div>
            </div>
            <div className="shivam-weather-picker" aria-label="हवामानासाठी शहर निवडा">
              <label htmlFor="shivam-weather-city">हवामानाचे शहर</label>
              <select id="shivam-weather-city" value={weatherCity} onChange={(event) => setWeatherCity(event.target.value)}>
                {weatherCities.map((city) => <option key={city.name} value={city.name}>{city.name}</option>)}
              </select>
            </div>
            <h2 className="text-sm font-medium mt-5 mb-2" style={{ color: 'var(--color-text-secondary)' }}>
              {getGreeting()}
            </h2>
            <p className="text-sm text-center max-w-sm mb-6" style={{ color: 'var(--color-text-secondary)' }}>
              तुमचा वैयक्तिक AI सहाय्यक. मी तुमची काय मदत करू?
            </p>

            {/* Quick action hints */}
            <div className="shivam-quick-actions flex gap-3">
              <button
                onClick={() => navigate('/data-sources')}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs cursor-pointer transition-colors"
                style={{
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
              >
                <Database size={14} style={{ color: 'var(--color-accent)' }} />
                डेटा स्रोत जोडा
              </button>
              <button
                onClick={() => { navigate('/data-sources'); setTimeout(() => window.dispatchEvent(new CustomEvent('switch-tab', { detail: 'messaging' })), 100); }}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs cursor-pointer transition-colors"
                style={{
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
              >
                <MessageSquare size={14} style={{ color: 'var(--color-accent)' }} />
                मेसेजिंग सुविधा सुरू करा
              </button>
            </div>
          </div>
        ) : (
          <div className="max-w-[var(--chat-max-width)] mx-auto px-4 py-6">
            {messages.map((msg, i) => {
              const isLastAssistant =
                i === messages.length - 1 && msg.role === 'assistant';
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLive={isLastAssistant && isCurrentChatStreaming}
                />
              );
            })}
            {(() => {
              if (!isCurrentChatStreaming || streamState.content !== '') return null;
              // For research messages the ResearchTimeline handles its own
              // pre-content loading state — suppress the generic dots.
              const last = messages[messages.length - 1];
              if (last?.role === 'assistant' && last.isResearch) return null;
              return (
                <div className="flex justify-start mb-4">
                  <StreamingDots phase={streamState.phase} />
                </div>
              );
            })()}
          </div>
        )}
      </div>
      <InputArea />
    </div>
  );
}
