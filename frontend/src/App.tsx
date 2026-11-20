import { useEffect, useState, useCallback, useRef } from 'react';
import { Routes, Route } from 'react-router';
import { Layout } from './components/Layout';
import { ChatPage } from './pages/ChatPage';
import { DashboardPage } from './pages/DashboardPage';
import { SettingsPage } from './pages/SettingsPage';
import { GetStartedPage } from './pages/GetStartedPage';
import { AgentsPage } from './pages/AgentsPage';
import { DataSourcesPage } from './pages/DataSourcesPage';
import { LogsPage } from './pages/LogsPage';
import { NotesPage } from './pages/NotesPage';
import { PhotoEditorPage } from './pages/PhotoEditorPage';
import { SmartConverterPage } from './pages/SmartConverterPage';
import { CommandPalette } from './components/CommandPalette';
import { SetupScreen } from './components/SetupScreen';
import { Toaster } from './components/ui/sonner';
import { useAppStore } from './lib/store';
import { fetchModels, fetchServerInfo, fetchSavings, submitSavings, isTauri } from './lib/api';
import { OptInModal } from './components/OptInModal';
import { UpdateChecker } from './components/Desktop/UpdateChecker';
import { track, hashId } from './lib/analytics';
import { offerAnalyticsChoice } from './lib/analytics-invitation';
import { SiteRemindersPage } from './pages/SiteRemindersPage';
import { useTtsStore } from './lib/tts';

export default function App() {
  const [setupDone, setSetupDone] = useState(!isTauri());
  const handleSetupReady = useCallback(() => {
    setSetupDone(true);
    // Only fire once per install — guard against setup screen re-appearing
    // on reinstalls or dev reloads.
    if (!localStorage.getItem('oj-setup-completed')) {
      localStorage.setItem('oj-setup-completed', '1');
      track('setup_completed', { preset: 'default' });
    }
  }, []);
  const prevModelRef = useRef<string>('');
  const setModels = useAppStore((s) => s.setModels);
  const setModelsLoading = useAppStore((s) => s.setModelsLoading);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const setServerInfo = useAppStore((s) => s.setServerInfo);
  const setSavings = useAppStore((s) => s.setSavings);
  const settings = useAppStore((s) => s.settings);
  const commandPaletteOpen = useAppStore((s) => s.commandPaletteOpen);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const optInEnabled = useAppStore((s) => s.optInEnabled);
  const optInDisplayName = useAppStore((s) => s.optInDisplayName);
  const optInEmail = useAppStore((s) => s.optInEmail);
  const optInAnonId = useAppStore((s) => s.optInAnonId);
  const optInModalSeen = useAppStore((s) => s.optInModalSeen);
  const optInModalOpen = useAppStore((s) => s.optInModalOpen);
  const setOptInModalOpen = useAppStore((s) => s.setOptInModalOpen);
  const markOptInModalSeen = useAppStore((s) => s.markOptInModalSeen);
  const savings = useAppStore((s) => s.savings);

  // Apply theme class to <html>
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('dark', 'light');
    if (settings.theme === 'dark') root.classList.add('dark');
    else if (settings.theme === 'light') root.classList.add('light');
  }, [settings.theme]);

  // Sync overlay conversations into the main app
  const importOverlay = useAppStore((s) => s.importOverlayConversation);
  useEffect(() => {
    if (!isTauri()) return;
    importOverlay();
    const interval = setInterval(importOverlay, 5000);
    return () => clearInterval(interval);
  }, [importOverlay]);

  // Reliable Android/Desktop model loading with retry and refresh
  useEffect(() => {
    let cancelled = false;
    let loading = false;
    let interval: ReturnType<typeof setInterval>;

    const loadModels = async (initial = false) => {
      if (loading || cancelled) return;
      loading = true;
      if (initial) setModelsLoading(true);

      try {
        for (let attempt = 0; attempt < 6 && !cancelled; attempt++) {
          try {
            const models = await fetchModels();
            if (!cancelled) setModels(models);
            return;
          } catch {
            if (attempt < 5) {
              await new Promise((resolve) => setTimeout(resolve, 2000));
            }
          }
        }
      } finally {
        if (!cancelled && initial) setModelsLoading(false);
        loading = false;
      }
    };

    const onVisible = () => {
      if (document.visibilityState === 'visible') void loadModels(false);
    };

    void loadModels(true);
    interval = setInterval(() => void loadModels(false), 60000);
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep server identity fresh when the app starts, regains focus, or becomes visible.
  useEffect(() => {
    let cancelled = false;
    let running = false;
    const refreshInfo = async () => {
      if (running || cancelled) return;
      running = true;
      try {
        const info = await fetchServerInfo();
        if (!cancelled) setServerInfo(info);
      } catch {
        // Health banner handles backend connectivity separately.
      } finally {
        running = false;
      }
    };
    void refreshInfo();
    const interval = setInterval(() => void refreshInfo(), 30000);
    const onFocus = () => void refreshInfo();
    const onVisible = () => {
      if (document.visibilityState === "visible") void refreshInfo();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [setServerInfo]);

  // Poll savings and optionally share to Supabase
  useEffect(() => {
    const refresh = () =>
      fetchSavings()
        .then((data) => {
          setSavings(data);
          if (optInEnabled && optInDisplayName && data) {
            const claudeEntry = data.per_provider.find(
              (p) => p.provider === 'claude-fable-5',
            );
            const dollarSavings = claudeEntry ? claudeEntry.total_cost : 0;
            const energySaved = data.per_provider.reduce(
              (sum, p) => sum + (p.energy_wh || 0),
              0,
            );
            const flopsSaved = data.per_provider.reduce(
              (sum, p) => sum + (p.flops || 0),
              0,
            );
            submitSavings({
              anon_id: optInAnonId,
              display_name: optInDisplayName,
              email: optInEmail,
              total_calls: data.total_calls,
              total_tokens: data.total_tokens,
              dollar_savings: dollarSavings,
              energy_wh_saved: energySaved,
              flops_saved: flopsSaved,
              token_counting_version: data.token_counting_version ?? 1,
            });
          }
        })
        .catch(() => {});
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [optInEnabled, optInDisplayName, optInEmail, optInAnonId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Wait for desktop setup before fetching identity or marking the dialog seen.
  useEffect(() => offerAnalyticsChoice({
    ready: setupDone,
    sharingModalSeen: optInModalSeen,
    open: () => setOptInModalOpen(true),
    markSharingModalSeen: markOptInModalSeen,
  }), [setupDone, optInModalSeen, setOptInModalOpen, markOptInModalSeen]);

  // Fire model_changed when the user switches models. First mount is
  // not a "change" — only emit when both prev and current are real and
  // differ.
  useEffect(() => {
    const prev = prevModelRef.current;
    const curr = selectedModel || '';
    prevModelRef.current = curr;
    if (!prev || !curr || prev === curr) return;
    void (async () => {
      const [fromHash, toHash] = await Promise.all([
        hashId(prev),
        hashId(curr),
      ]);
      track('model_changed', {
        from_model_hash: fromHash,
        to_model_hash: toHash,
      });
    })();
  }, [selectedModel]);

  // app_opened — one-shot per app launch, fires after analytics has had
  // a chance to initialize. platform + version are super-properties
  // registered in analytics.ts initAnalytics, so no per-call props needed.
  useEffect(() => {
    const t = setTimeout(() => {
      track('app_opened', {});
    }, 500);
    return () => clearTimeout(t);
  }, []);

  // Read today's site tasks aloud once when SHIVAM opens each day.
  useEffect(() => {
    const now = new Date();
    const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const marker = `shivam-site-reminders-announced-${day}`;
    if (localStorage.getItem(marker)) return;
    try {
      const saved = JSON.parse(localStorage.getItem('shivam-site-reminders-v1') || '[]');
      if (!Array.isArray(saved)) return;
      const due = saved.filter((item: { date?: string; done?: boolean }) => !item.done && typeof item.date === 'string' && item.date <= day);
      if (!due.length) return;
      const speech = 'आजची आणि बाकी राहिलेली साइटची कामे. ' + due.map((item: { title?: string; site?: string }, index: number) => `${index + 1}. ${item.site ? item.site + ' येथे, ' : ''}${item.title || 'काम'}.`).join(' ');
      localStorage.setItem(marker, '1');
      const timer = window.setTimeout(() => { void useTtsStore.getState().speak('site-reminders-auto-' + day, speech); }, 1800);
      return () => window.clearTimeout(timer);
    } catch { /* Ignore malformed local reminder data. */ }
  }, []);

  const toggleSystemPanel = useAppStore((s) => s.toggleSystemPanel);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
        e.preventDefault();
        toggleSystemPanel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen, toggleSystemPanel]);


  if (!setupDone) {
    return <SetupScreen onReady={handleSetupReady} />;
  }

  return (
    <>
      <UpdateChecker />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ChatPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="get-started" element={<GetStartedPage />} />
          <Route path="data-sources" element={<DataSourcesPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="logs" element={<LogsPage />} />
              <Route path="notes" element={<NotesPage />} />
          <Route path="photo-editor" element={<PhotoEditorPage />} />
          <Route path="smart-converter" element={<SmartConverterPage />} />
          <Route path="site-reminders" element={<SiteRemindersPage />} />
        </Route>
      </Routes>
      <Toaster position="bottom-right" />
      {commandPaletteOpen && <CommandPalette />}
      {optInModalOpen && (
        <OptInModal onClose={() => setOptInModalOpen(false)} />
      )}
    </>
  );
}
