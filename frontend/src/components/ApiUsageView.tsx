import { useEffect, useState } from 'react';
import { RefreshCw, Activity, CheckCircle2, XCircle, Gauge, Clock, Server } from 'lucide-react';
import { solarApi } from '../api/client';
import type { ApiUsageResponse } from '../types/solar';

function formatLocalTime(raw?: string | null): string {
  if (!raw) return '—';
  const hasTz = /(?:Z|[+-]\d{2}:\d{2})$/.test(raw);
  const d = new Date(hasTz ? raw : `${raw}Z`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

export function ApiUsageView() {
  const [usage, setUsage] = useState<ApiUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await solarApi.getApiUsage(150);
      setUsage(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load API usage');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading && !usage) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-sm text-slate-500">
        Loading DeyeCloud API call history...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 px-4 py-3 text-sm">
        {error}
      </div>
    );
  }

  if (!usage) return null;

  const successRate =
    usage.total_calls > 0 ? ((usage.success_calls / usage.total_calls) * 100).toFixed(1) : '100.0';
  const quotaPct = ((usage.calls_this_month / usage.monthly_quota) * 100).toFixed(3);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold">DeyeCloud API Call Log &amp; Quota Monitor</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Every outbound request sent to india-developer.deyecloud.com with call counts, latency, and timestamps
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium transition"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Reload Log
        </button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Total Calls Logged</span>
            <Activity className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono">{usage.total_calls}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {usage.success_calls} OK • {usage.error_calls} Errors
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Calls Today</span>
            <Clock className="h-4 w-4 text-sky-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono">{usage.calls_today}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Since 00:00 UTC</div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Monthly Quota</span>
            <Server className="h-4 w-4 text-violet-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono">{usage.calls_this_month}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {quotaPct}% of {usage.monthly_quota.toLocaleString()} limit
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Last Minute (QPM)</span>
            <Gauge className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono">
            {usage.calls_last_minute} / {usage.qpm_limit}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Rate limit headroom</div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Success Rate</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {successRate}%
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">HTTP &amp; API responses</div>
        </div>
      </div>

      {/* Endpoint Breakdown */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
        <h3 className="font-semibold text-sm mb-3">API Calls by Endpoint</h3>
        {usage.endpoints.length === 0 ? (
          <div className="text-xs text-slate-400 py-6 text-center">
            No DeyeCloud API calls recorded yet. Click Refresh or Discover to make a call.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <th className="py-2 pr-4">Endpoint</th>
                  <th className="py-2 pr-4">Total Calls</th>
                  <th className="py-2 pr-4">Success</th>
                  <th className="py-2 pr-4">Errors</th>
                  <th className="py-2 pr-4">Avg Latency</th>
                  <th className="py-2">Last Called</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-xs">
                {usage.endpoints.map((ep) => (
                  <tr key={ep.endpoint}>
                    <td className="py-2.5 pr-4 font-semibold text-amber-600 dark:text-amber-400">
                      {ep.endpoint}
                    </td>
                    <td className="py-2.5 pr-4">{ep.total_calls}</td>
                    <td className="py-2.5 pr-4 text-emerald-600 dark:text-emerald-400">
                      {ep.success_calls}
                    </td>
                    <td className="py-2.5 pr-4 text-rose-500">{ep.error_calls}</td>
                    <td className="py-2.5 pr-4">{ep.avg_duration_ms.toFixed(0)} ms</td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">
                      {formatLocalTime(ep.last_called_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recent Call Log */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
        <h3 className="font-semibold text-sm mb-3">
          Recent API Calls ({usage.recent_calls.length})
        </h3>
        {usage.recent_calls.length === 0 ? (
          <div className="text-xs text-slate-400 py-6 text-center">
            No API calls logged yet.
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white dark:bg-slate-900">
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <th className="py-2 pr-4">Time</th>
                  <th className="py-2 pr-4">Method</th>
                  <th className="py-2 pr-4">Endpoint</th>
                  <th className="py-2 pr-4">HTTP</th>
                  <th className="py-2 pr-4">Duration</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-xs">
                {usage.recent_calls.map((c) => (
                  <tr key={c.id}>
                    <td className="py-2 pr-4 whitespace-nowrap text-slate-500 dark:text-slate-400">
                      {formatLocalTime(c.created_at)}
                    </td>
                    <td className="py-2 pr-4 font-semibold">{c.method}</td>
                    <td className="py-2 pr-4 text-sky-600 dark:text-sky-400">{c.endpoint}</td>
                    <td className="py-2 pr-4">{c.status_code ?? '—'}</td>
                    <td className="py-2 pr-4">{c.duration_ms.toFixed(0)} ms</td>
                    <td className="py-2 pr-4">
                      {c.success ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="h-3.5 w-3.5" /> OK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-500">
                          <XCircle className="h-3.5 w-3.5" /> Error
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-rose-500 max-w-xs truncate">
                      {c.error_message || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
