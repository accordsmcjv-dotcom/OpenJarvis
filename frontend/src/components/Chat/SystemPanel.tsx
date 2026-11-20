import { useState, useEffect, useCallback } from 'react';
import { Capacitor, registerPlugin } from '@capacitor/core';
import { toast } from 'sonner';
import {
  Zap,
  Activity,
  Thermometer,
  DollarSign,
  TrendingDown,
  Cloud,
  HardDrive,
  Hash,
  Mic,
  MicOff,
  X,
  Trophy,
  ExternalLink,
  ScanEye,
  ImagePlus,
  Loader2,
} from 'lucide-react';
import { useAppStore } from '../../lib/store';
import { apiFetch } from '../../lib/api';

interface ScreenUnderstandingApi {
  captureAndReadScreen(): Promise<{ text: string; message: string }>;
  pickImageAndRead(): Promise<{ text: string; message: string }>;
  pickImageAndDescribe(): Promise<{ text: string; message: string }>;
}
const ScreenUnderstanding = registerPlugin<ScreenUnderstandingApi>('ScreenUnderstanding');

interface EnergyData {
  total_energy_j?: number;
  energy_per_token_j?: number;
  avg_power_w?: number;
  cpu_temp_c?: number | null;
  gpu_temp_c?: number | null;
}

interface TelemetryStats {
  total_requests?: number;
  total_tokens?: number;
}

const CLOUD_PRICING = [
  { name: 'GPT-5.6 Sol', input: 5.00, output: 30.00, primary: true },
  { name: 'Claude Fable 5', input: 10.00, output: 50.00, primary: false },
  { name: 'Gemini 3.1 Pro', input: 2.00, output: 12.00, primary: false },
];

export function SystemPanel() {
  const savings = useAppStore((s) => s.savings);
  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);
  const optInEnabled = useAppStore((s) => s.optInEnabled);
  const setOptInModalOpen = useAppStore((s) => s.setOptInModalOpen);
  const liveEnergy = useAppStore((s) => s.liveEnergy);
  const [energy, setEnergy] = useState<EnergyData | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryStats | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<'listening' | 'capturing' | 'thinking' | 'off'>('off');
  const [screenBusy, setScreenBusy] = useState(false);
  const [screenText, setScreenText] = useState('');
  const isAndroid = Capacitor.getPlatform() === 'android';

  const readScreen = useCallback(async () => {
    if (!isAndroid || screenBusy) return;
    setScreenBusy(true);
    setScreenText('');
    try {
      const result = await ScreenUnderstanding.captureAndReadScreen();
      setScreenText(result.text || 'स्क्रीनवर वाचता येण्याजोगा मजकूर आढळला नाही.');
      toast.success('स्क्रीनवरील मजकूर वाचला.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'स्क्रीन वाचता आली नाही.');
    } finally {
      setScreenBusy(false);
    }
  }, [isAndroid, screenBusy]);

  const readScene = useCallback(async () => {
    if (!isAndroid || screenBusy) return;
    setScreenBusy(true);
    setScreenText('');
    try {
      const result = await ScreenUnderstanding.pickImageAndDescribe();
      setScreenText(result.text || 'फोटोतील दृश्य ओळखता आले नाही.');
      toast.success('फोटोतील दृश्याचे विश्लेषण पूर्ण.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'फोटोचे विश्लेषण करता आले नाही.');
    } finally {
      setScreenBusy(false);
    }
  }, [isAndroid, screenBusy]);

  const readImage = useCallback(async () => {
    if (!isAndroid || screenBusy) return;
    setScreenBusy(true);
    setScreenText('');
    try {
      const result = await ScreenUnderstanding.pickImageAndRead();
      setScreenText(result.text || 'फोटोमध्ये वाचता येण्याजोगा मजकूर आढळला नाही.');
      toast.success('फोटोवरील मजकूर वाचला.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'फोटो वाचता आला नाही.');
    } finally {
      setScreenBusy(false);
    }
  }, [isAndroid, screenBusy]);

  useEffect(() => {
    const handleVoiceStatus = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail === 'listening' || detail === 'capturing' || detail === 'thinking' || detail === 'off') {
        setVoiceStatus(detail);
      }
    };
    window.addEventListener('shivamWakeStatus', handleVoiceStatus);
    return () => window.removeEventListener('shivamWakeStatus', handleVoiceStatus);
  }, []);

  const voiceStatusLabel = {
    listening: '“Shivam” ऐकत आहे',
    capturing: 'आदेश ऐकत आहे',
    thinking: 'विचार करत आहे',
    off: 'आवाज सेवा बंद',
  }[voiceStatus];

  const fetchData = useCallback(async () => {
    try {
      const [energyRes, telRes] = await Promise.allSettled([
        apiFetch('/v1/telemetry/energy').then((r) => (r.ok ? r.json() : null)),
        apiFetch('/v1/telemetry/stats').then((r) => (r.ok ? r.json() : null)),
      ]);
      if (energyRes.status === 'fulfilled' && energyRes.value) {
        setEnergy(energyRes.value as EnergyData);
      }
      if (telRes.status === 'fulfilled' && telRes.value) {
        setTelemetry(telRes.value as TelemetryStats);
      }
    } catch {
      // best-effort
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Re-fetch energy/telemetry when savings updates (after a chat message)
  useEffect(() => {
    if (savings) fetchData();
  }, [savings, fetchData]);

  const promptK = (savings?.total_prompt_tokens ?? 0) / 1000;
  const completionK = (savings?.total_completion_tokens ?? 0) / 1000;

  return (
    <div
      className="flex flex-col h-full overflow-y-auto"
      style={{
        width: 280,
        minWidth: 280,
        background: 'var(--color-bg)',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <span className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--color-text-secondary)' }}>
          SHIVAM प्रणाली
        </span>
        <button
          onClick={toggleSystemPanel}
          className="p-1 rounded-md transition-colors cursor-pointer"
          style={{ color: 'var(--color-text-tertiary)' }}
          title="Close panel"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex flex-col gap-4 p-4">
        {/* Session Stats */}
        <section>
          <h4 className="text-[11px] font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            सत्र माहिती
          </h4>
          <div className="grid grid-cols-2 gap-2">
            <MiniStat icon={Hash} label="विनंत्या" value={String(savings?.total_calls ?? telemetry?.total_requests ?? 0)} />
            <MiniStat icon={Hash} label="उत्तर टोकन्स" value={formatNumber(savings?.total_completion_tokens ?? telemetry?.total_tokens ?? 0)} />
          </div>
        </section>

        {/* Voice assistant status */}
        <section>
          <h4 className="text-[11px] font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            आवाज सहाय्यक
          </h4>
          <MiniStat
            icon={voiceStatus === 'off' ? MicOff : Mic}
            label="SHIVAM Voice"
            value={voiceStatusLabel}
          />
        </section>

        {/* Screen understanding */}
        <section>
          <h4 className="text-[11px] font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            स्क्रीन समजून घेणे
          </h4>
          <button
            type="button"
            onClick={readScreen}
            disabled={!isAndroid || screenBusy}
            className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-medium disabled:opacity-50"
            style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)', border: '1px solid var(--color-border)' }}
          >
            {screenBusy ? <Loader2 size={14} className="animate-spin" /> : <ScanEye size={14} />}
            {screenBusy ? 'स्क्रीन वाचत आहे…' : 'स्क्रीन वाचा'}
          </button>
          <button
            type="button"
            onClick={readImage}
            disabled={!isAndroid || screenBusy}
            className="w-full mt-2 flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-medium disabled:opacity-50"
            style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
          >
            {screenBusy ? <Loader2 size={14} className="animate-spin" /> : <ImagePlus size={14} />}
            {screenBusy ? 'फोटो वाचत आहे…' : 'फोटोमधील मजकूर वाचा'}
          </button>
          <button
            type="button"
            onClick={readScene}
            disabled={!isAndroid || screenBusy}
            className="w-full mt-2 flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-xs font-medium disabled:opacity-50"
            style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
          >
            {screenBusy ? <Loader2 size={14} className="animate-spin" /> : <ScanEye size={14} />}
            {screenBusy ? 'दृश्य समजून घेत आहे…' : 'फोटोतील वस्तू व दृश्य ओळखा'}
          </button>
          <p className="text-[10px] mt-1.5" style={{ color: 'var(--color-text-tertiary)' }}>
            स्क्रीन वाचणे, फोटोतील मजकूर काढणे आणि फोटोतील सामान्य वस्तू/दृश्य ओळखणे ही प्रक्रिया फोनवर होते.
          </p>
          {screenText && (
            <div className="mt-2 rounded-lg p-2.5 text-xs whitespace-pre-wrap break-words max-h-48 overflow-y-auto" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>
              {screenText}
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('shivamInsertScreenText', { detail: screenText }))} className="block mt-2 font-semibold" style={{ color: 'var(--color-accent)' }}>
                हा मजकूर चॅटमध्ये आणा
              </button>
            </div>
          )}
        </section>

        {/* Device */}
        <section>
          <h4 className="text-[11px] font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            उपकरण स्थिती
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {energy?.cpu_temp_c != null && (
              <MiniStat icon={Thermometer} label="CPU तापमान" value={String(Math.round(energy.cpu_temp_c))} unit="°C" />
            )}
            {energy?.gpu_temp_c != null && (
              <MiniStat icon={Thermometer} label="GPU तापमान" value={String(Math.round(energy.gpu_temp_c))} unit="°C" />
            )}
            <MiniStat
              icon={Zap}
              label="वीज वापर"
              value={(liveEnergy?.power_w ?? energy?.avg_power_w ?? 0).toFixed(1)}
              unit="W"
            />
            <MiniStat
              icon={Activity}
              label="ऊर्जा"
              value={(
                ((liveEnergy?.energy_j ?? energy?.total_energy_j ?? 0) / 1000)
              ).toFixed(1)}
              unit="kJ"
            />
          </div>
        </section>


        {/* Cost Comparison */}
        <section>
          <h4 className="text-[11px] font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
            खर्च तुलना
          </h4>

          {/* Local */}
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2 mb-2"
            style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent)' }}
          >
            <HardDrive size={14} style={{ color: 'var(--color-accent)' }} />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>स्थानिक</div>
            </div>
            <div className="text-sm font-semibold" style={{ color: 'var(--color-success)' }}>
              ${(savings?.local_cost ?? 0).toFixed(4)}
            </div>
          </div>

          {/* Cloud providers */}
          <div className="flex flex-col gap-1.5">
            {CLOUD_PRICING.map((provider) => {
              const cost = (promptK * provider.input) / 1000 + (completionK * provider.output) / 1000;
              const saved = cost - (savings?.local_cost ?? 0);
              return (
                <div
                  key={provider.name}
                  className="flex items-center gap-2 rounded-lg px-3 py-2"
                  style={{
                    background: provider.primary ? 'var(--color-bg-secondary)' : 'var(--color-bg-secondary)',
                    border: provider.primary ? '1px solid var(--color-border-accent, var(--color-accent))' : '1px solid transparent',
                  }}
                >
                  <Cloud size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-xs truncate"
                      style={{
                        color: provider.primary ? 'var(--color-text)' : 'var(--color-text-secondary)',
                        fontWeight: provider.primary ? 500 : 400,
                      }}
                    >
                      {provider.name}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-xs font-mono" style={{ color: 'var(--color-text)' }}>
                      ${cost.toFixed(4)}
                    </div>
                    {saved > 0.0001 && (
                      <div className="text-[9px] flex items-center gap-0.5 justify-end" style={{ color: 'var(--color-success)' }}>
                        <TrendingDown size={8} />
                        ${saved.toFixed(4)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>


        </section>

        {/* Leaderboard / Share */}
        <section>
          <h4
            className="text-[11px] font-medium uppercase tracking-wide mb-2"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            क्रमवारी
          </h4>

          <button
            onClick={() => setOptInModalOpen(true)}
            className="w-full flex items-center gap-2 rounded-lg px-3 py-2.5 transition-colors cursor-pointer"
            style={{
              background: optInEnabled
                ? 'var(--color-accent-subtle)'
                : 'var(--color-bg-secondary)',
              border: optInEnabled
                ? '1px solid var(--color-accent)'
                : '1px solid var(--color-border)',
            }}
          >
            <Trophy
              size={14}
              style={{
                color: optInEnabled ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
              }}
            />
            <span
              className="text-xs flex-1 text-left"
              style={{
                color: optInEnabled ? 'var(--color-accent)' : 'var(--color-text-secondary)',
              }}
            >
              {optInEnabled ? 'बचत शेअर होत आहे' : 'बचत शेअर करा'}
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded-full"
              style={{
                background: optInEnabled ? 'var(--color-accent)' : 'var(--color-bg-tertiary, var(--color-bg-secondary))',
                color: optInEnabled ? 'white' : 'var(--color-text-tertiary)',
              }}
            >
              {optInEnabled ? 'ON' : 'OFF'}
            </span>
          </button>

          <a
            href="https://open-jarvis.github.io/OpenJarvis/leaderboard"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 mt-1.5 px-3 py-1.5 text-[11px] rounded-lg transition-colors"
            style={{ color: 'var(--color-text-tertiary)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-accent)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
          >
            <ExternalLink size={10} />
            View Leaderboard
          </a>
        </section>
      </div>
    </div>
  );
}

function MiniStat({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: typeof Zap;
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div
      className="rounded-lg px-2.5 py-2"
      style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}
    >
      <div className="flex items-center gap-1 mb-0.5">
        <Icon size={10} style={{ color: 'var(--color-accent)' }} />
        <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
          {label}
        </span>
      </div>
      <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {value}
        {unit && (
          <span className="text-[10px] font-normal ml-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}
