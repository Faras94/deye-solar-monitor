import { Cpu, Home, Sun } from 'lucide-react';
import type { InverterLive, PVChannelReading } from '../types/solar';

function SolarPanelTile({ pv }: { pv: PVChannelReading }) {
  const isAvailable = pv.power !== null || pv.voltage !== null || pv.current !== null;
  const watts = pv.power;
  const isGenerating = watts !== null && watts > 0;

  return (
    <div
      className={`relative rounded-xl border p-2.5 flex flex-col items-center justify-between transition ${
        !isAvailable
          ? 'border-dashed border-slate-300 dark:border-slate-800 bg-slate-100/40 dark:bg-slate-900/30 opacity-50'
          : isGenerating
          ? 'border-amber-400/60 bg-gradient-to-b from-sky-950 via-slate-900 to-slate-950 text-white shadow-md shadow-amber-500/10'
          : 'border-slate-300 dark:border-slate-700 bg-gradient-to-b from-slate-800 via-slate-900 to-slate-950 text-white'
      }`}
    >
      {/* Solar cell SVG grid background */}
      <svg
        viewBox="0 0 100 64"
        className="w-full h-14 rounded-lg border border-sky-400/30 bg-sky-950/60 overflow-hidden"
        aria-hidden="true"
      >
        <defs>
          <pattern id={`grid-${pv.channel}`} width="20" height="16" patternUnits="userSpaceOnUse">
            <path
              d="M 20 0 L 0 0 0 16"
              fill="none"
              stroke="rgba(56, 189, 248, 0.28)"
              strokeWidth="0.8"
            />
          </pattern>
        </defs>
        <rect width="100" height="64" fill={`url(#grid-${pv.channel})`} />
        {isGenerating && (
          <circle cx="84" cy="12" r="5" fill="rgba(251, 191, 36, 0.85)" />
        )}
      </svg>

      {/* Panel Label & Wattage Overlay */}
      <div className="mt-2 w-full text-center">
        <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-300 px-0.5">
          <span className="font-semibold">PV{pv.channel}</span>
          <span>{pv.voltage !== null ? `${pv.voltage.toFixed(1)}V` : '—'}</span>
        </div>
        <div
          className={`mt-0.5 text-base font-bold font-mono ${
            watts === null
              ? 'text-slate-400'
              : isGenerating
              ? 'text-amber-400'
              : 'text-slate-200'
          }`}
        >
          {watts !== null ? `${watts.toFixed(0)} W` : 'N/A'}
        </div>
        <div className="text-[10px] font-mono text-slate-400">
          {pv.current !== null ? `${pv.current.toFixed(1)} A` : 'Unavailable'}
        </div>
      </div>
    </div>
  );
}

export function SolarFlowDiagram({
  inverters,
  totalPowerW,
  totalDailyKwh,
}: {
  inverters: InverterLive[];
  totalPowerW: number | null;
  totalDailyKwh: number | null;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-5">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Sun className="h-4 w-4 text-amber-500" />
            Solar Array &amp; Power Flow
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Individual PV panel wattages flowing into each microinverter and combined AC output
          </p>
        </div>
        <span className="text-[11px] px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
          Measured DeyeCloud PV telemetry only
        </span>
      </div>

      {/* 3 Microinverter Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {inverters.map((inv) => {
          const isOnline = inv.status === 'online';
          const activePower = inv.current_power_w ?? 0;
          const isFlowing = activePower > 0;

          return (
            <div
              key={inv.device_sn}
              className="flex flex-col items-center rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 p-4"
            >
              {/* Individual Solar Panels (PV1..PV4) */}
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-2.5 w-full">
                {inv.pv_inputs.map((pv) => (
                  <SolarPanelTile key={pv.channel} pv={pv} />
                ))}
              </div>

              {/* Flow Connector: Panels -> Microinverter */}
              <div className="flex flex-col items-center my-2">
                <div
                  className={`w-0.5 h-5 ${
                    isFlowing
                      ? 'bg-gradient-to-b from-amber-400 to-emerald-400 animate-pulse'
                      : 'bg-slate-300 dark:bg-slate-700'
                  }`}
                />
                <div
                  className={`w-2 h-2 rotate-45 border-r-2 border-b-2 -mt-1.5 ${
                    isFlowing ? 'border-emerald-400' : 'border-slate-300 dark:border-slate-700'
                  }`}
                />
              </div>

              {/* Microinverter Node */}
              <div
                className={`w-full rounded-xl border px-3.5 py-2.5 flex items-center justify-between ${
                  isOnline
                    ? 'border-emerald-500/40 bg-emerald-500/10'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Cpu className="h-4 w-4 text-amber-500 shrink-0" />
                  <div>
                    <div className="text-xs font-semibold">{inv.name.split(' (')[0]}</div>
                    <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                      {inv.device_sn}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold font-mono text-amber-600 dark:text-amber-400">
                    {inv.current_power_w !== null ? `${inv.current_power_w.toFixed(0)} W` : 'N/A'}
                  </div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400">
                    {inv.daily_energy_kwh !== null ? `${inv.daily_energy_kwh.toFixed(2)} kWh` : '—'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Combined AC Bus Flow */}
      <div className="mt-4 flex flex-col items-center">
        <div className="hidden lg:flex items-center justify-around w-2/3">
          {inverters.map((inv) => (
            <div
              key={inv.device_sn}
              className={`w-0.5 h-5 ${
                (inv.current_power_w ?? 0) > 0
                  ? 'bg-emerald-400 animate-pulse'
                  : 'bg-slate-300 dark:bg-slate-700'
              }`}
            />
          ))}
        </div>
        <div className="hidden lg:block w-2/3 h-0.5 bg-slate-300 dark:bg-slate-700" />
        <div className="w-0.5 h-5 bg-amber-500" />

        <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-6 py-3 flex items-center gap-4">
          <div className="h-10 w-10 rounded-xl bg-amber-500 text-white flex items-center justify-center">
            <Home className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Combined AC Solar Output
            </div>
            <div className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
              {totalPowerW !== null ? `${totalPowerW.toFixed(0)} W` : 'N/A'}
              <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">
                ({totalDailyKwh !== null ? `${totalDailyKwh.toFixed(2)} kWh today` : '—'})
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
