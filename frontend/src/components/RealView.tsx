import { useEffect, useMemo, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Cpu, Zap, BatteryCharging, Leaf, CheckCircle2, Sun } from 'lucide-react';
import { solarApi } from '../api/client';
import type { HistoricalPoint, InverterLive, LiveDashboardResponse, PVChannelReading } from '../types/solar';

// Physical panel wiring: only actually connected PV channels per microinverter (8 panels total)
const CONNECTED_CHANNELS: Record<string, number[]> = {
  '260605A076': [2, 3, 4], // PV1 has no panel connected
  '260603A1D5': [1, 2, 3, 4], // All 4 panels connected
  '260505A373': [2], // PV1 has no panel connected (1 panel on PV2)
};

const RATED_WATTS: Record<string, number> = {
  '260605A076': 2200,
  '260603A1D5': 2200,
  '260505A373': 1000,
};

function getPvEnergyKwh(inverter: InverterLive, channel: number): number | null {
  const key = `TotalProduction${channel}`;
  const pt = inverter.raw_points.find((p) => p.key === key);
  if (!pt || pt.value === null || pt.value === undefined || pt.value === '') return null;
  const num = Number(pt.value);
  return Number.isFinite(num) ? num : null;
}

function RealPanelCard({
  panelNumber,
  pv,
  pvEnergyKwh,
  inverterStatus,
}: {
  panelNumber: number;
  pv: PVChannelReading;
  pvEnergyKwh: number | null;
  inverterStatus: string;
}) {
  const watts = pv.power;
  const isGenerating = watts !== null && watts > 0;
  const isOnline = inverterStatus === 'online';

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700/80 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-white p-3.5 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between text-xs mb-2.5">
        <div>
          <span className="font-semibold text-slate-100">Panel {panelNumber}</span>
          <span className="ml-1.5 text-[10px] font-mono text-sky-300/80">(PV{pv.channel})</span>
        </div>
        <span
          className={`inline-flex items-center gap-1 text-[11px] font-medium ${
            isOnline ? 'text-emerald-400' : 'text-slate-400'
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              isOnline ? 'bg-emerald-400' : 'bg-slate-500'
            }`}
          />
          {isOnline ? 'Online' : inverterStatus}
        </span>
      </div>

      {/* Panel Visual + Wattage */}
      <div className="flex items-center gap-3.5">
        <svg
          viewBox="0 0 96 64"
          className={`w-24 h-16 shrink-0 rounded-lg border ${
            isGenerating
              ? 'border-sky-400/70 shadow-md shadow-sky-500/20'
              : 'border-sky-500/35'
          } bg-gradient-to-br from-sky-700 via-blue-900 to-slate-900`}
          aria-hidden="true"
        >
          <defs>
            <pattern id={`real-cell-${panelNumber}`} width="16" height="16" patternUnits="userSpaceOnUse">
              <path
                d="M 16 0 L 0 0 0 16"
                fill="none"
                stroke="rgba(186, 230, 253, 0.35)"
                strokeWidth="0.9"
              />
            </pattern>
          </defs>
          <rect width="96" height="64" fill={`url(#real-cell-${panelNumber})`} />
          <line x1="0" y1="32" x2="96" y2="32" stroke="rgba(186, 230, 253, 0.55)" strokeWidth="1" />
          <line x1="48" y1="0" x2="48" y2="64" stroke="rgba(186, 230, 253, 0.55)" strokeWidth="1" />
        </svg>

        <div className="min-w-0 flex-1">
          <div
            className={`text-2xl font-bold font-mono tracking-tight ${
              isGenerating ? 'text-amber-400' : 'text-slate-100'
            }`}
          >
            {watts !== null ? `${watts.toFixed(0)} W` : 'N/A'}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11px] font-mono text-slate-300">
            <span>{pv.voltage !== null ? `${pv.voltage.toFixed(1)} V` : '— V'}</span>
            <span>•</span>
            <span>{pv.current !== null ? `${pv.current.toFixed(1)} A` : '— A'}</span>
          </div>
          <div className="mt-0.5 text-[11px] font-mono text-emerald-400">
            {pvEnergyKwh !== null ? `⚡ ${pvEnergyKwh.toFixed(2)} kWh` : '⚡ —'}
          </div>
        </div>
      </div>

      {/* Subtle bottom accent wave */}
      <div
        className={`mt-3 h-1 rounded-full ${
          isGenerating
            ? 'bg-gradient-to-r from-emerald-400 via-amber-400 to-emerald-400'
            : 'bg-gradient-to-r from-emerald-500/30 via-sky-500/30 to-emerald-500/30'
        }`}
      />
    </div>
  );
}

export function RealView({ live }: { live: LiveDashboardResponse }) {
  const [todayHistory, setTodayHistory] = useState<HistoricalPoint[]>([]);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    solarApi
      .getHistory({ granularity: 'intraday', startDate: today, endDate: today })
      .then((res) => setTodayHistory(res.records))
      .catch(() => {});
  }, [live.last_sync_at]);

  // Build ordered 8-panel groups
  const inverterGroups = useMemo(() => {
    let panelCounter = 1;
    return live.inverters.map((inv) => {
      const connected = CONNECTED_CHANNELS[inv.device_sn] ?? [1, 2, 3, 4];
      const panels = connected
        .map((ch) => {
          const pv = inv.pv_inputs.find((p) => p.channel === ch);
          if (!pv) return null;
          const num = panelCounter++;
          return {
            panelNumber: num,
            pv,
            pvEnergyKwh: getPvEnergyKwh(inv, ch),
          };
        })
        .filter((x): x is NonNullable<typeof x> => x !== null);

      return {
        inverter: inv,
        ratedKw: (RATED_WATTS[inv.device_sn] ?? 2000) / 1000,
        panels,
      };
    });
  }, [live.inverters]);

  const totalPanels = inverterGroups.reduce((acc, g) => acc + g.panels.length, 0);
  const totalPowerW = live.summary.total_current_power_w;
  const totalDailyKwh = live.summary.total_daily_energy_kwh;
  const co2SavedKg = totalDailyKwh !== null ? totalDailyKwh * 0.82 : null;

  const trendData = useMemo(() => {
    const byTime: Record<string, { time: string; powerW: number }> = {};
    for (const r of todayHistory) {
      const t = r.period_key.length >= 16 ? r.period_key.slice(11, 16) : r.period_key;
      if (!byTime[r.period_key]) byTime[r.period_key] = { time: t, powerW: 0 };
      byTime[r.period_key].powerW += r.power_w ?? 0;
    }
    return Object.entries(byTime)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, v]) => ({ time: v.time, powerW: Number(v.powerW.toFixed(0)) }));
  }, [todayHistory]);

  return (
    <div className="space-y-5">
      {/* Top Banner */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center">
            <Sun className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold">Real View — {totalPanels} Connected Solar Panels</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Showing only physically wired panels (unconnected PV1 ports hidden)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/20 px-3.5 py-2">
            <Zap className="h-4 w-4 text-amber-500" />
            <div>
              <div className="text-[10px] uppercase text-slate-500 dark:text-slate-400">
                Total Generation
              </div>
              <div className="text-sm font-bold font-mono text-amber-600 dark:text-amber-400">
                {totalPowerW !== null ? `${totalPowerW.toFixed(0)} W` : 'N/A'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3.5 py-2">
            <BatteryCharging className="h-4 w-4 text-emerald-500" />
            <div>
              <div className="text-[10px] uppercase text-slate-500 dark:text-slate-400">
                Today&apos;s Energy
              </div>
              <div className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {totalDailyKwh !== null ? `${totalDailyKwh.toFixed(2)} kWh` : 'N/A'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-xl bg-teal-500/10 border border-teal-500/20 px-3.5 py-2">
            <Leaf className="h-4 w-4 text-teal-500" />
            <div>
              <div className="text-[10px] uppercase text-slate-500 dark:text-slate-400">
                CO₂ Saved Today
              </div>
              <div className="text-sm font-bold font-mono text-teal-600 dark:text-teal-400">
                {co2SavedKg !== null ? `${co2SavedKg.toFixed(2)} kg` : 'N/A'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3 Microinverter Rows with Connected Panels */}
      <div className="space-y-4">
        {inverterGroups.map(({ inverter, ratedKw, panels }) => {
          const isOnline = inverter.status === 'online';
          const gridCols =
            panels.length === 1
              ? 'grid-cols-1 max-w-md'
              : panels.length === 3
              ? 'grid-cols-1 md:grid-cols-3'
              : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';

          return (
            <section
              key={inverter.device_sn}
              className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-4 shadow-sm"
            >
              {/* Inverter Row Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-sky-500/15 text-sky-500 flex items-center justify-center">
                    <Cpu className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-semibold text-sm flex items-center gap-2">
                      <span>{inverter.name}</span>
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium capitalize ${
                          isOnline
                            ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                            : 'bg-rose-500/15 text-rose-600 dark:text-rose-400'
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            isOnline ? 'bg-emerald-500' : 'bg-rose-500'
                          }`}
                        />
                        {inverter.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {ratedKw.toFixed(1)} kW Rated • {panels.length} Panel{panels.length > 1 ? 's' : ''} Connected
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6 text-right">
                  <div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400">Current Power</div>
                    <div className="text-base font-bold font-mono text-amber-600 dark:text-amber-400">
                      {inverter.current_power_w !== null
                        ? `${inverter.current_power_w.toFixed(0)} W`
                        : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400">Today&apos;s Energy</div>
                    <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400">
                      {inverter.daily_energy_kwh !== null
                        ? `${inverter.daily_energy_kwh.toFixed(2)} kWh`
                        : 'N/A'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Connected Panels */}
              <div className={`grid ${gridCols} gap-3.5`}>
                {panels.map((p) => (
                  <RealPanelCard
                    key={`${inverter.device_sn}-pv${p.pv.channel}`}
                    panelNumber={p.panelNumber}
                    pv={p.pv}
                    pvEnergyKwh={p.pvEnergyKwh}
                    inverterStatus={inverter.status}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>

      {/* Bottom Row: Today's Power Trend + System Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
          <h3 className="font-semibold text-sm mb-3">Total Power Trend (Today)</h3>
          {trendData.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-xs text-slate-400">
              Intraday trend will appear as 5-minute samples accumulate today.
            </div>
          ) : (
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit=" W" />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="powerW"
                    name="Total Power (W)"
                    stroke="#0ea5e9"
                    fill="#0ea5e9"
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 flex flex-col justify-between space-y-4">
          <div>
            <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              System Summary
            </h3>
            <dl className="space-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="text-slate-500 dark:text-slate-400">Total Panels</dt>
                <dd className="font-mono font-semibold">{totalPanels}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500 dark:text-slate-400">Microinverters</dt>
                <dd className="font-mono font-semibold">{live.inverters.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500 dark:text-slate-400">Inverter Rating</dt>
                <dd className="font-mono font-semibold">5.4 kW</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500 dark:text-slate-400">Layout</dt>
                <dd className="font-mono">3 + 4 + 1 Panels</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-700 dark:text-emerald-300">
            <strong>{live.summary.online_count}/{live.summary.total_devices}</strong> microinverters online. Unconnected PV1 ports are excluded from this view.
          </div>
        </div>
      </div>
    </div>
  );
}
