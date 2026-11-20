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
import { Capacitor, registerPlugin } from '@capacitor/core';

interface ShivamLocationPlugin {
  getCurrentLocation(): Promise<{ latitude: number; longitude: number; accuracy: number }>;
}

const ShivamLocation = registerPlugin<ShivamLocationPlugin>('ShivamLocation');

interface ShivamDevicePlugin {
  getNotificationAccessStatus(): Promise<{ granted: boolean }>;
  setNotificationReadingEnabled(options: { enabled: boolean }): Promise<{ enabled: boolean }>;
  getWatchmanStatus(): Promise<{ enabled: boolean }>;
  startWatchman(): Promise<{ started: boolean }>;
  stopWatchman(): Promise<{ stopping: boolean }>;
  openNotificationAccessSettings(): Promise<void>;
  addListener(eventName: 'notificationReceived', listener: (event: { packageName: string; title: string; text: string }) => void): Promise<{ remove: () => Promise<void> }>;
  getTelemetry(): Promise<{
    batteryPercent?: number; charging?: boolean; chargerConnected?: boolean; batteryTemperatureC?: number;
    storageFreeGb?: number; storageTotalGb?: number;
    memoryAvailableGb?: number; memoryTotalGb?: number; lowMemory?: boolean;
    thermalStatus?: string; deviceModel?: string; androidVersion?: string;
    bluetoothAudioConnected?: boolean; wiredHeadphonesConnected?: boolean; headphonesConnected?: boolean;
    networkConnected?: boolean; internetValidated?: boolean; wifiEnabled?: boolean; wifiConnected?: boolean; networkTransport?: string;
    ringerMode?: string; dndAccessGranted?: boolean; dndStatus?: string; screenInteractive?: boolean; deviceLocked?: boolean;
  }>;
}
const ShivamDevice = registerPlugin<ShivamDevicePlugin>('ShivamDevice');

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
  const [batteryCharging, setBatteryCharging] = useState<boolean | null>(null);
  const [deviceTelemetry, setDeviceTelemetry] = useState<Awaited<ReturnType<ShivamDevicePlugin['getTelemetry']>> | null>(null);
  const [notificationAccessGranted, setNotificationAccessGranted] = useState(false);
  const [watchmanEnabled, setWatchmanEnabled] = useState(false);
  const [watchmanBusy, setWatchmanBusy] = useState(false);
  const [notificationReadingEnabled, setNotificationReadingEnabled] = useState(() => {
    try { return localStorage.getItem('shivam_notification_reading') === 'true'; } catch { return false; }
  });
  const [lastSmartNotification, setLastSmartNotification] = useState('');
  const previousChargerState = useRef<boolean | null>(null);
  const lowBatteryAlerted = useRef(false);
  const fullBatteryAlerted = useRef(false);
  const hotBatteryAlerted = useRef(false);
  const previousHeadphonesState = useRef<boolean | null>(null);
  const previousInternetState = useRef<boolean | null>(null);
  const previousWifiState = useRef<boolean | null>(null);
  const previousRingerMode = useRef<string | null>(null);
  const previousDndStatus = useRef<string | null>(null);
  const lowStorageAlerted = useRef(false);
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
  const [weatherLocation, setWeatherLocation] = useState<{ name: string; lat: number; lon: number } | null>(null);
  const [locationBusy, setLocationBusy] = useState(false);
  const [locationMessage, setLocationMessage] = useState('');
  const [weatherSummary, setWeatherSummary] = useState('LOADING');
  const [weatherHumidity, setWeatherHumidity] = useState<number | null>(null);
  const [weatherBusy, setWeatherBusy] = useState(false);
  const [weatherForecast, setWeatherForecast] = useState<Array<{ date: string; max: number; min: number; rain: number }>>([]);
  const [weatherAlert, setWeatherAlert] = useState('');

  const requestCurrentLocation = async () => {
    setLocationBusy(true);
    setLocationMessage('स्थान मिळवत आहे…');
    try {
      if (Capacitor.isNativePlatform()) {
        // Native Android plugin requests runtime permission only after the user taps this button.
        const position = await ShivamLocation.getCurrentLocation();
        setWeatherLocation({ name: 'MY LOCATION', lat: position.latitude, lon: position.longitude });
      } else {
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
          if (!navigator.geolocation) {
            reject(new Error('या डिव्हाइसवर Location उपलब्ध नाही'));
            return;
          }
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: false,
            timeout: 15000,
            maximumAge: 5 * 60 * 1000,
          });
        });
        setWeatherLocation({ name: 'MY LOCATION', lat: position.coords.latitude, lon: position.coords.longitude });
      }
      setLocationMessage('सध्याचे स्थान वापरत आहे');
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      setLocationMessage(/denied|permission|परवानगी/i.test(message)
        ? 'Location परवानगी नाकारली. फोनच्या Settings मधून परवानगी द्या किंवा शहर निवडा.'
        : (message || 'स्थान मिळाले नाही. पुन्हा प्रयत्न करा.'));
    } finally {
      setLocationBusy(false);
    }
  };

  useEffect(() => {
    const city = weatherLocation ?? (weatherCities.find((item) => item.name === weatherCity) ?? weatherCities[0]);
    let cancelled = false;
    const loadWeather = async () => {
      setWeatherBusy(true);
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${city.lat}&longitude=${city.lon}&current=temperature_2m,relative_humidity_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=7&timezone=Asia%2FKolkata`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Weather unavailable');
        const data = await response.json() as {
          current?: { temperature_2m?: number; relative_humidity_2m?: number; weather_code?: number };
          daily?: { time?: string[]; temperature_2m_max?: number[]; temperature_2m_min?: number[]; precipitation_probability_max?: number[] };
        };
        const current = data.current;
        if (!current || typeof current.temperature_2m !== 'number') throw new Error('Weather data missing');
        const code = current.weather_code ?? -1;
        const condition = code === 0 ? 'CLEAR' : [1, 2, 3].includes(code) ? 'CLOUDY'
          : [45, 48].includes(code) ? 'FOG' : [51, 53, 55, 56, 57].includes(code) ? 'DRIZZLE'
          : [61, 63, 65, 66, 67, 80, 81, 82].includes(code) ? 'RAIN'
          : [71, 73, 75, 77, 85, 86].includes(code) ? 'SNOW'
          : [95, 96, 99].includes(code) ? 'STORM' : 'WEATHER';
        if (!cancelled) {
          setWeatherSummary(`${Math.round(current.temperature_2m)}°C · ${condition}`);
          setWeatherHumidity(typeof current.relative_humidity_2m === 'number' ? Math.round(current.relative_humidity_2m) : null);
          const daily = data.daily;
          if (daily?.time && daily.temperature_2m_max && daily.temperature_2m_min) {
            const forecast = daily.time.map((date, index) => ({
              date,
              max: Math.round(daily.temperature_2m_max?.[index] ?? 0),
              min: Math.round(daily.temperature_2m_min?.[index] ?? 0),
              rain: Math.round(daily.precipitation_probability_max?.[index] ?? 0),
            }));
            setWeatherForecast(forecast);
            const today = forecast[0];
            const rainyDay = forecast.find((day) => day.rain >= 70);
            const hotDay = forecast.find((day) => day.max >= 38);
            const coldDay = forecast.find((day) => day.min <= 12);
            setWeatherAlert(today && today.rain >= 60
              ? 'आज पावसाची शक्यता जास्त आहे. बाहेर पडताना छत्री ठेवा.'
              : today && today.max >= 38
                ? 'आज उष्णता जास्त असू शकते. पाणी पित राहा.'
                : today && today.min <= 12
                  ? 'आज थंडी जाणवेल. उबदार कपडे वापरा.'
                  : rainyDay ? new Date(rainyDay.date + 'T12:00:00').toLocaleDateString('mr-IN', { weekday: 'long' }) + ' पावसाची शक्यता जास्त आहे.'
                    : hotDay ? 'पुढील आठवड्यात उष्ण दिवस अपेक्षित आहेत.'
                      : coldDay ? 'पुढील आठवड्यात थंडी वाढू शकते.'
                        : '');
          }
        }
      } catch {
        if (!cancelled) { setWeatherSummary('UNAVAILABLE'); setWeatherHumidity(null); setWeatherForecast([]); setWeatherAlert(''); }
      } finally {
        if (!cancelled) setWeatherBusy(false);
      }
    };
    void loadWeather();
    const timer = window.setInterval(loadWeather, 15 * 60 * 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [weatherCity, weatherLocation]);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let active = true;
    let listenerHandle: { remove: () => Promise<void> } | null = null;
    void ShivamDevice.getNotificationAccessStatus()
      .then((status) => { if (active) setNotificationAccessGranted(status.granted); })
      .catch(() => undefined);
    void ShivamDevice.getWatchmanStatus()
      .then((status) => { if (active) setWatchmanEnabled(status.enabled); })
      .catch(() => undefined);
    void ShivamDevice.addListener('notificationReceived', (event) => {
      if (!active || !notificationReadingEnabled) return;
      const packageName = (event.packageName || '').toLowerCase();
      if (/(bank|banking|wallet|paytm|phonepe|gpay|authenticator|password|credential|whatsapp|telegram|signal|messenger|messages|sms)/i.test(packageName)) return;
      const title = (event.title || '').trim();
      const body = (event.text || '').trim();
      const message = [title, body].filter(Boolean).join(' — ');
      if (!message) return;
      if (/(otp|one[- ]time|verification code|password|पासवर्ड|पिन कोड|pin code|transaction)/i.test(message)) return;
      if (/\b\d{4,8}\b/.test(message) && /(code|verify|verification|otp)/i.test(message)) return;
      setLastSmartNotification(message);
      void useTtsStore.getState().speak(`notification-${Date.now()}`, `नवीन सूचना. ${message}`);
    }).then((handle) => { listenerHandle = handle; })
      .catch(() => undefined);
    return () => {
      active = false;
      if (listenerHandle) void listenerHandle.remove();
    };
  }, [notificationReadingEnabled]);

  const toggleWatchman = async () => {
    if (watchmanBusy) return;
    setWatchmanBusy(true);
    try {
      if (watchmanEnabled) {
        await ShivamDevice.stopWatchman();
        setWatchmanEnabled(false);
      } else {
        await ShivamDevice.startWatchman();
        setWatchmanEnabled(true);
      }
    } catch {
      setLastSmartNotification('Smart Watchman सुरू किंवा बंद करता आला नाही. Notification परवानगी तपासा.');
    } finally {
      setWatchmanBusy(false);
    }
  };

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    void ShivamDevice.setNotificationReadingEnabled({ enabled: notificationReadingEnabled }).catch(() => undefined);
  }, [notificationReadingEnabled]);

  const enableNotificationAccess = async () => {
    try {
      await ShivamDevice.openNotificationAccessSettings();
    } catch {
      setLastSmartNotification('Notification Access सेटिंग उघडता आली नाही.');
    }
  };

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let cancelled = false;
    const refreshTelemetry = async () => {
      try {
        const info = await ShivamDevice.getTelemetry();
        if (!cancelled) {
          setDeviceTelemetry(info);
          if (typeof info.storageFreeGb === 'number' && typeof info.storageTotalGb === 'number' && info.storageTotalGb > 0) {
            const lowStorage = info.storageFreeGb <= Math.max(5, info.storageTotalGb * 0.1);
            if (lowStorage && !lowStorageAlerted.current) {
              lowStorageAlerted.current = true;
              void useTtsStore.getState().speak(`storage-low-${Date.now()}`, `फोनमधील जागा कमी उरली आहे. फक्त ${info.storageFreeGb.toFixed(1)} जीबी जागा उपलब्ध आहे.`);
            } else if (!lowStorage && info.storageFreeGb > Math.max(6, info.storageTotalGb * 0.12)) {
              lowStorageAlerted.current = false;
            }
          }
          if (typeof info.ringerMode === 'string') {
            const previous = previousRingerMode.current;
            if (previous !== null && previous !== info.ringerMode) {
              const labels: Record<string, string> = { SILENT: 'सायलेंट मोड', VIBRATE: 'व्हायब्रेशन मोड', NORMAL: 'रिंग मोड' };
              void useTtsStore.getState().speak(`ringer-${info.ringerMode}-${Date.now()}`, `फोनचा आवाज ${labels[info.ringerMode] ?? info.ringerMode} मध्ये बदलला आहे.`);
            }
            previousRingerMode.current = info.ringerMode;
          }
          if (typeof info.dndStatus === 'string' && info.dndStatus !== 'UNKNOWN') {
            const previous = previousDndStatus.current;
            if (previous !== null && previous !== info.dndStatus) {
              const labels: Record<string, string> = { OFF: 'बंद', TOTAL_SILENCE: 'पूर्ण शांतता', ALARMS_ONLY: 'फक्त अलार्म', PRIORITY_ONLY: 'प्राधान्य सूचना' };
              void useTtsStore.getState().speak(`dnd-${info.dndStatus}-${Date.now()}`, `डू नॉट डिस्टर्ब मोड ${labels[info.dndStatus] ?? info.dndStatus}.`);
            }
            previousDndStatus.current = info.dndStatus;
          }
          if (typeof info.internetValidated === 'boolean') {
            const previous = previousInternetState.current;
            if (previous !== null && previous !== info.internetValidated) {
              const message = info.internetValidated
                ? 'इंटरनेट कनेक्शन पुन्हा सुरू झाले आहे.'
                : 'इंटरनेट कनेक्शन उपलब्ध नाही.';
              void useTtsStore.getState().speak(`internet-${info.internetValidated ? 'online' : 'offline'}-${Date.now()}`, message);
            }
            previousInternetState.current = info.internetValidated;
          }
          if (typeof info.wifiConnected === 'boolean') {
            const previous = previousWifiState.current;
            if (previous !== null && previous !== info.wifiConnected) {
              const message = info.wifiConnected ? 'Wi-Fi जोडले गेले आहे.' : 'Wi-Fi डिस्कनेक्ट झाले आहे.';
              void useTtsStore.getState().speak(`wifi-${info.wifiConnected ? 'connected' : 'disconnected'}-${Date.now()}`, message);
            }
            previousWifiState.current = info.wifiConnected;
          }
          if (typeof info.internetValidated === 'boolean') {
            setNetworkOnline(info.internetValidated);
            setNetworkType(info.networkTransport ?? (info.internetValidated ? 'CONNECTED' : 'OFFLINE'));
          }
          if (typeof info.headphonesConnected === 'boolean') {
            const previous = previousHeadphonesState.current;
            if (previous !== null && previous !== info.headphonesConnected) {
              const message = info.headphonesConnected
                ? (info.bluetoothAudioConnected ? 'Bluetooth हेडफोन जोडले गेले आहेत.' : 'हेडफोन जोडले गेले आहेत.')
                : 'हेडफोन डिस्कनेक्ट झाले आहेत.';
              void useTtsStore.getState().speak(`headphones-${info.headphonesConnected ? 'connected' : 'disconnected'}-${Date.now()}`, message);
            }
            previousHeadphonesState.current = info.headphonesConnected;
          }
          if (typeof info.chargerConnected === 'boolean') {
            const previous = previousChargerState.current;
            if (previous === null) {
              const message = info.chargerConnected ? 'चार्जर जोडलेला आहे.' : 'चार्जर जोडलेला नाही.';
              void useTtsStore.getState().speak(`charger-status-${Date.now()}`, message);
            } else if (previous !== info.chargerConnected) {
              const message = info.chargerConnected ? 'चार्जर जोडला गेला आहे.' : 'चार्जर काढला गेला आहे.';
              void useTtsStore.getState().speak(`charger-${info.chargerConnected ? 'connected' : 'disconnected'}-${Date.now()}`, message);
            }
            previousChargerState.current = info.chargerConnected;
          }
          if (typeof info.batteryPercent === 'number') {
            setBatteryLevel(info.batteryPercent);
            if (info.batteryPercent <= 20 && info.charging === false && !lowBatteryAlerted.current) {
              lowBatteryAlerted.current = true;
              void useTtsStore.getState().speak(`battery-low-${Date.now()}`, `बॅटरी ${info.batteryPercent} टक्के आहे. कृपया फोन चार्ज करा.`);
            } else if (info.batteryPercent > 25 || info.charging === true) {
              lowBatteryAlerted.current = false;
            }

            if (info.batteryPercent >= 100 && info.charging === true && !fullBatteryAlerted.current) {
              fullBatteryAlerted.current = true;
              void useTtsStore.getState().speak(`battery-full-${Date.now()}`, 'बॅटरी पूर्ण चार्ज झाली आहे. चार्जर काढू शकता.');
            } else if (info.batteryPercent < 98 || info.charging === false) {
              fullBatteryAlerted.current = false;
            }
          }
          if (typeof info.batteryTemperatureC === 'number') {
            if (info.batteryTemperatureC >= 45 && !hotBatteryAlerted.current) {
              hotBatteryAlerted.current = true;
              void useTtsStore.getState().speak(`battery-hot-${Date.now()}`, 'फोनची बॅटरी खूप गरम झाली आहे. काही वेळ फोनचा वापर थांबवा.');
            } else if (info.batteryTemperatureC <= 42) {
              hotBatteryAlerted.current = false;
            }
          }
          if (typeof info.charging === 'boolean') setBatteryCharging(info.charging);
        }
      } catch {
        if (!cancelled) setDeviceTelemetry(null);
      }
    };
    void refreshTelemetry();
    const timer = window.setInterval(refreshTelemetry, 3_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    type BatteryLike = EventTarget & { level: number; charging: boolean; addEventListener: (type: string, listener: EventListener) => void; removeEventListener: (type: string, listener: EventListener) => void };
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
      if (battery) { setBatteryLevel(Math.round(battery.level * 100)); setBatteryCharging(battery.charging); }
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
      battery.addEventListener('chargingchange', updateBattery);
    }).catch(() => setBatteryLevel(null));
    return () => {
      active = false;
      window.clearInterval(clockTimer);
      window.removeEventListener('online', updateNetwork);
      window.removeEventListener('offline', updateNetwork);
      connection?.removeEventListener('change', updateNetwork);
      battery?.removeEventListener('levelchange', updateBattery);
      battery?.removeEventListener('chargingchange', updateBattery);
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
  const [proactiveNoticeDismissed, setProactiveNoticeDismissed] = useState(false);
  const proactiveNotice = !networkOnline
    ? { key: 'offline', message: 'इंटरनेट कनेक्शन बंद आहे. ऑनलाइन सुविधा सध्या उपलब्ध नसू शकतात.' }
    : batteryLevel !== null && batteryLevel <= 20 && batteryCharging === false
      ? { key: 'battery', message: 'बॅटरी २०% किंवा त्यापेक्षा कमी आहे. फोन चार्ज करण्याची तयारी ठेवा.' }
      : weatherAlert
        ? { key: 'weather', message: weatherAlert }
        : null;

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
      {proactiveNotice && !proactiveNoticeDismissed && (
        <div
          className="mx-4 mb-2 flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm shrink-0"
          role="status"
          style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-border)' }}
        >
          <span aria-hidden="true">✦</span>
          <span style={{ color: 'var(--color-text-secondary)', flex: 1 }}>
            <b style={{ color: 'var(--color-text-primary)' }}>SHIVAM सूचना · </b>{proactiveNotice.message}
          </span>
          <button
            type="button"
            onClick={() => setProactiveNoticeDismissed(true)}
            className="p-1 rounded cursor-pointer"
            style={{ color: 'var(--color-text-tertiary)', background: 'transparent', border: 'none' }}
            aria-label="सूचना बंद करा"
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
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">ϟ</span><span className="shivam-glass-label">BATTERY</span><b>{deviceTelemetry?.batteryPercent === undefined && batteryLevel === null ? 'N/A' : `${deviceTelemetry?.batteryPercent ?? batteryLevel}% · ${(deviceTelemetry?.charging ?? batteryCharging) === null ? '—' : (deviceTelemetry?.charging ?? batteryCharging) ? 'CHARGING' : 'ON BATTERY'}`}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">⌁</span><span className="shivam-glass-label">NETWORK</span><b>{networkOnline ? networkType.toUpperCase() : 'OFFLINE'}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">◷</span><span className="shivam-glass-label">LOCAL TIME</span><b>{hudClock}</b></div>
              <div className="shivam-glass-cell">
                <span className="shivam-glass-icon">♧</span><span className="shivam-glass-label">SMART NOTIFICATIONS</span>
                <b>{notificationAccessGranted ? 'ACCESS ENABLED' : 'ACCESS OFF'} · {notificationReadingEnabled ? 'VOICE ON' : 'VOICE OFF'}</b>
                <button type="button" onClick={() => {
                  const next = !notificationReadingEnabled;
                  setNotificationReadingEnabled(next);
                  try { localStorage.setItem('shivam_notification_reading', String(next)); } catch { /* storage may be unavailable */ }
                  if (!next) setLastSmartNotification('');
                }} className="text-xs underline" style={{ color: 'var(--color-accent)' }}>
                  {notificationReadingEnabled ? 'सूचना वाचणे बंद करा' : 'सूचना वाचणे सुरू करा'}
                </button>
                {!notificationAccessGranted && <button type="button" onClick={enableNotificationAccess} className="text-xs underline" style={{ color: 'var(--color-accent)' }}>परवानगी सेट करा</button>}
              </div>
              <div className="shivam-glass-cell">
                <span className="shivam-glass-icon">◉</span><span className="shivam-glass-label">SHIVAM SMART WATCHMAN</span>
                <b>{watchmanEnabled ? 'MONITORING ON' : 'MONITORING OFF'}</b>
                {Capacitor.isNativePlatform() && <button type="button" disabled={watchmanBusy} onClick={() => void toggleWatchman()} className="text-xs underline disabled:opacity-50" style={{ color: 'var(--color-accent)' }}>
                  {watchmanBusy ? 'कृपया थांबा…' : watchmanEnabled ? 'Watchman बंद करा' : 'Watchman सुरू करा'}
                </button>}
              </div>
              {lastSmartNotification && <div className="shivam-glass-cell"><span className="shivam-glass-icon">✉</span><span className="shivam-glass-label">LAST NOTIFICATION</span><b>{lastSmartNotification}</b></div>}
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">☼</span><span className="shivam-glass-label">WEATHER · {(weatherLocation?.name ?? weatherCity).toUpperCase()}</span><b>{weatherBusy && weatherSummary === 'LOADING' ? 'LOADING' : weatherSummary}</b></div>
              <div className="shivam-glass-cell"><span className="shivam-glass-icon">♨</span><span className="shivam-glass-label">HUMIDITY</span><b>{weatherHumidity === null ? "N/A" : `${weatherHumidity}%`}</b></div>
              {deviceTelemetry?.storageFreeGb !== undefined && <div className="shivam-glass-cell"><span className="shivam-glass-icon">▤</span><span className="shivam-glass-label">DEVICE STORAGE · FREE</span><b>{deviceTelemetry.storageFreeGb.toFixed(1)} / {(deviceTelemetry.storageTotalGb ?? 0).toFixed(1)} GB</b></div>}
              {deviceTelemetry?.memoryAvailableGb !== undefined && <div className="shivam-glass-cell"><span className="shivam-glass-icon">▦</span><span className="shivam-glass-label">AVAILABLE RAM</span><b>{deviceTelemetry.memoryAvailableGb.toFixed(1)} / {(deviceTelemetry.memoryTotalGb ?? 0).toFixed(1)} GB</b></div>}
              {deviceTelemetry?.batteryTemperatureC !== undefined && <div className="shivam-glass-cell"><span className="shivam-glass-icon">♨</span><span className="shivam-glass-label">BATTERY TEMP</span><b>{deviceTelemetry.batteryTemperatureC.toFixed(1)}°C</b></div>}
              {deviceTelemetry?.thermalStatus && <div className="shivam-glass-cell"><span className="shivam-glass-icon">⌁</span><span className="shivam-glass-label">THERMAL STATUS</span><b>{deviceTelemetry.thermalStatus}</b></div>}
              {deviceTelemetry?.ringerMode && <div className="shivam-glass-cell"><span className="shivam-glass-icon">♫</span><span className="shivam-glass-label">RINGER</span><b>{deviceTelemetry.ringerMode}</b></div>}
              {deviceTelemetry?.dndAccessGranted && deviceTelemetry.dndStatus && <div className="shivam-glass-cell"><span className="shivam-glass-icon">◉</span><span className="shivam-glass-label">DO NOT DISTURB</span><b>{deviceTelemetry.dndStatus}</b></div>}
              {deviceTelemetry?.screenInteractive !== undefined && <div className="shivam-glass-cell"><span className="shivam-glass-icon">▣</span><span className="shivam-glass-label">SCREEN</span><b>{deviceTelemetry.screenInteractive ? 'ON' : 'OFF'}</b></div>}
              {deviceTelemetry?.deviceLocked !== undefined && <div className="shivam-glass-cell"><span className="shivam-glass-icon">⌑</span><span className="shivam-glass-label">LOCK</span><b>{deviceTelemetry.deviceLocked ? 'LOCKED' : 'UNLOCKED'}</b></div>}
              {deviceTelemetry?.deviceModel && <div className="shivam-glass-cell"><span className="shivam-glass-icon">▣</span><span className="shivam-glass-label">DEVICE</span><b>{deviceTelemetry.deviceModel} · Android {deviceTelemetry.androidVersion ?? '—'}</b></div>}
            </div>
            <div className="shivam-weather-picker" aria-label="हवामानाचे स्थान निवडा">
              <button type="button" onClick={requestCurrentLocation} disabled={locationBusy} className="shivam-location-button">
                {locationBusy ? 'स्थान मिळवत आहे…' : '⌖ माझे सध्याचे स्थान वापरा'}
              </button>
              {locationMessage && <span className="shivam-location-message" role="status">{locationMessage}</span>}
              <label htmlFor="shivam-weather-city">किंवा शहर निवडा</label>
              <select id="shivam-weather-city" value={weatherCity} onChange={(event) => { setWeatherCity(event.target.value); setWeatherLocation(null); setLocationMessage(''); }}>
                {weatherCities.map((city) => <option key={city.name} value={city.name}>{city.name}</option>)}
              </select>
            </div>
            {weatherAlert && (
              <div className="shivam-weather-alert" role="status">
                <span aria-hidden="true">⚠</span><b>SHIVAM सूचना</b><span>{weatherAlert}</span>
              </div>
            )}
            {weatherForecast.length > 0 && (
              <div className="shivam-weather-forecast" aria-label="पुढील सात दिवसांचा हवामान अंदाज">
                {weatherForecast.map((day) => (
                  <div className="shivam-weather-day" key={day.date}>
                    <span>{new Date(`${day.date}T12:00:00`).toLocaleDateString('mr-IN', { weekday: 'short' })}</span>
                    <b>{day.max}°</b>
                    <span>{day.min}°</span>
                    <small>☂ {day.rain}%</small>
                  </div>
                ))}
              </div>
            )}
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
