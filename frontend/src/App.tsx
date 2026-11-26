import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, WifiOff } from 'lucide-react';
import { solarApi } from './api/client';
import { Header, type TabKey } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { SolarFlowDiagram } from './components/SolarFlowDiagram';
import { InverterCard } from './components/InverterCard';
import { RealView } from './components/RealView';
import { HistoryView } from './components/HistoryView';
import { DeviceManagementView } from './components/DeviceManagementView';
import { ApiUsageView } from './components/ApiUsageView';
import type { LiveDashboardResponse } from './types/solar';

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('deye-theme');
    return saved ? saved === 'dark' : true;
  });
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState<boolean>(false);
  const [intervalMinutes, setIntervalMinutes] = useState<number>(5);
  const [live, setLive] = useState<LiveDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('deye-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    solarApi
      .getScheduler()
      .then((cfg) => {
        setAutoRefreshEnabled(cfg.enabled);
        setIntervalMinutes(cfg.interval_minutes);
      })
      .catch(() => {
        // Keep defaults if scheduler endpoint is temporarily unreachable
      });
  }, []);

  const loadLive = useCallback(async () => {
    try {
      const data = await solarApi.getLive();
      setLive(data);
      setError(data.last_error || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reach backend API');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLive();
    if (!autoRefreshEnabled) return;
    const ms = Math.max(1, intervalMinutes) * 60 * 1000;
    const timer = window.setInterval(loadLive, ms);
    return () => window.clearInterval(timer);
  }, [loadLive, autoRefreshEnabled, intervalMinutes]);

  const handleToggleAutoRefresh = async () => {
    const nextEnabled = !autoRefreshEnabled;
    setAutoRefreshEnabled(nextEnabled);
    try {
      const updated = await solarApi.updateScheduler({
        enabled: nextEnabled,
        interval_minutes: intervalMinutes,
      });
      setAutoRefreshEnabled(updated.enabled);
      setIntervalMinutes(updated.interval_minutes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update auto-refresh');
    }
  };

  const handleChangeIntervalMinutes = async (minutes: number) => {
    setIntervalMinutes(minutes);
    try {
      const updated = await solarApi.updateScheduler({
        enabled: autoRefreshEnabled,
        interval_minutes: minutes,
      });
      setAutoRefreshEnabled(updated.enabled);
      setIntervalMinutes(updated.interval_minutes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update refresh interval');
    }
  };

  const handleManualRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const col = await solarApi.collectNow();
      if (col.errors.length > 0) {
        setError(col.errors.join(' | '));
      }
      await loadLive();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Manual collection failed');
    } finally {
      setRefreshing(false);
    }
  };

  const configuredDevices = live?.inverters.map((i) => i.device_sn) ?? [
    '260605A076',
    '260603A1D5',
    '260505A373',
  ];

  const offlineDevices = live?.inverters.filter((i) => i.status === 'offline' || i.status === 'alert') ?? [];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 transition-colors">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        darkMode={darkMode}
        onToggleDark={() => setDarkMode((d) => !d)}
        onManualRefresh={handleManualRefresh}
        refreshing={refreshing}
        lastSyncAt={live?.last_sync_at}
        lastSyncStatus={live?.last_sync_status}
        autoRefreshEnabled={autoRefreshEnabled}
        intervalMinutes={intervalMinutes}
        onToggleAutoRefresh={handleToggleAutoRefresh}
        onChangeIntervalMinutes={handleChangeIntervalMinutes}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 px-4 py-3 text-sm flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {offlineDevices.length > 0 && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300 px-4 py-3 text-sm flex items-center gap-2.5">
            <WifiOff className="h-4 w-4 shrink-0" />
            <span>
              Offline / Alert device(s):{' '}
              <strong>{offlineDevices.map((d) => d.device_sn).join(', ')}</strong>
            </span>
          </div>
        )}

        {activeTab === 'dashboard' && (
          <>
            {loading && !live ? (
              <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-sm text-slate-500">
                Loading solar telemetry...
              </div>
            ) : live ? (
              <>
                <SummaryCards summary={live.summary} />
                <SolarFlowDiagram
                  inverters={live.inverters}
                  totalPowerW={live.summary.total_current_power_w}
                  totalDailyKwh={live.summary.total_daily_energy_kwh}
                />
                <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                  {live.inverters.map((inv) => (
                    <InverterCard key={inv.device_sn} inverter={inv} />
                  ))}
                </section>
              </>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 p-12 text-center text-sm text-slate-500">
                No telemetry available yet. Configure your backend `.env` credentials and click Refresh.
              </div>
            )}
          </>
        )}

        {activeTab === 'realview' && live && <RealView live={live} />}

        {activeTab === 'history' && <HistoryView configuredDevices={configuredDevices} />}

        {activeTab === 'devices' && <DeviceManagementView />}

        {activeTab === 'usage' && <ApiUsageView />}
      </main>
    </div>
  );
}

export default App;
