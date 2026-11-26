import { useEffect, useState } from 'react';
import { RefreshCw, Sun, Moon, Activity, History, Settings2, Power, LayoutGrid, Server } from 'lucide-react';

export type TabKey = 'dashboard' | 'realview' | 'history' | 'devices' | 'usage';

interface HeaderProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  darkMode: boolean;
  onToggleDark: () => void;
  onManualRefresh: () => void;
  refreshing: boolean;
  lastSyncAt?: string | null;
  lastSyncStatus?: string | null;
  autoRefreshEnabled: boolean;
  intervalMinutes: number;
  onToggleAutoRefresh: () => void;
  onChangeIntervalMinutes: (minutes: number) => void;
}

function formatLocalSync(raw?: string | null): string {
  if (!raw) return 'Never';
  const hasTz = /(?:Z|[+-]\d{2}:\d{2})$/.test(raw);
  const date = new Date(hasTz ? raw : `${raw}Z`);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

export function Header({
  activeTab,
  onTabChange,
  darkMode,
  onToggleDark,
  onManualRefresh,
  refreshing,
  lastSyncAt,
  lastSyncStatus,
  autoRefreshEnabled,
  intervalMinutes,
  onToggleAutoRefresh,
  onChangeIntervalMinutes,
}: HeaderProps) {
  const formattedSync = formatLocalSync(lastSyncAt);
  const [draftMinutes, setDraftMinutes] = useState<string>(String(intervalMinutes));

  useEffect(() => {
    setDraftMinutes(String(intervalMinutes));
  }, [intervalMinutes]);

  const commitMinutes = () => {
    const parsed = Math.round(Number(draftMinutes));
    if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 120 && parsed !== intervalMinutes) {
      onChangeIntervalMinutes(parsed);
    } else {
      setDraftMinutes(String(intervalMinutes));
    }
  };

  const navItems: Array<{ key: TabKey; label: string; icon: typeof Activity }> = [
    { key: 'dashboard', label: 'Live Dashboard', icon: Activity },
    { key: 'realview', label: 'Real View', icon: LayoutGrid },
    { key: 'history', label: 'History & Analytics', icon: History },
    { key: 'devices', label: 'Devices & Mappings', icon: Settings2 },
    { key: 'usage', label: 'API Usage', icon: Server },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center">
              <Sun className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">Deye Solar Monitor</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                India Cloud • 3 Microinverters •{' '}
                {autoRefreshEnabled ? `Auto-refresh ${intervalMinutes}m` : 'Auto-refresh OFF'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onToggleDark}
            className="lg:hidden p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl overflow-x-auto">
          {navItems.map(({ key, label, icon: Icon }) => {
            const active = activeTab === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => onTabChange(key)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition ${
                  active
                    ? 'bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="flex flex-wrap items-center justify-between lg:justify-end gap-2.5">
          {/* Auto-Refresh ON/OFF + Interval Minutes */}
          <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 px-2 py-1">
            <button
              type="button"
              onClick={onToggleAutoRefresh}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                autoRefreshEnabled
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
              }`}
              title="Turn auto-refresh on or off"
            >
              <Power className="h-3.5 w-3.5" />
              Auto: {autoRefreshEnabled ? 'ON' : 'OFF'}
            </button>

            <div className="flex items-center gap-1 pl-1">
              <input
                type="number"
                min={1}
                max={120}
                value={draftMinutes}
                onChange={(e) => setDraftMinutes(e.target.value)}
                onBlur={commitMinutes}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    commitMinutes();
                    (e.target as HTMLInputElement).blur();
                  }
                }}
                className="w-12 px-1.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-xs font-mono text-center"
                aria-label="Auto refresh interval in minutes"
              />
              <span className="text-[11px] text-slate-500 dark:text-slate-400 pr-1">min</span>
            </div>
          </div>

          <div className="text-right hidden sm:block">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Last Sync:{' '}
              <span className="font-medium text-slate-700 dark:text-slate-200">{formattedSync}</span>
            </div>
            {lastSyncStatus && (
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Status: {lastSyncStatus}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={onManualRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white text-sm font-medium shadow-sm transition"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Syncing...' : 'Refresh'}
          </button>

          <button
            type="button"
            onClick={onToggleDark}
            className="hidden lg:inline-flex p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
