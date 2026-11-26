import { Cpu, Thermometer, Zap } from 'lucide-react';
import type { InverterLive } from '../types/solar';
import { PvInputCard } from './PvInputCard';

function val(v: number | null | undefined, unit: string, decimals = 2): string {
  if (v === null || v === undefined) return 'N/A';
  return `${v.toFixed(decimals)} ${unit}`;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    online: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
    offline: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30',
    alert: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
    unknown: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize ${
        styles[status] || styles.unknown
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === 'online'
            ? 'bg-emerald-500'
            : status === 'offline'
            ? 'bg-rose-500'
            : status === 'alert'
            ? 'bg-amber-500'
            : 'bg-slate-400'
        }`}
      />
      {status}
    </span>
  );
}

export function InverterCard({ inverter }: { inverter: InverterLive }) {
  return (
    <article className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base">{inverter.name}</h3>
            <p className="text-xs font-mono text-slate-500 dark:text-slate-400">
              SN: {inverter.device_sn}
              {inverter.rated_power_w ? ` • Rated ${inverter.rated_power_w.toFixed(0)} W` : ''}
            </p>
          </div>
        </div>
        <StatusBadge status={inverter.status} />
      </div>

      {/* Primary Inverter Telemetry */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-xl bg-amber-500/10 p-3">
          <div className="text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1">
            <Zap className="h-3.5 w-3.5 text-amber-500" /> Current Power
          </div>
          <div className="mt-1 text-lg font-bold text-amber-600 dark:text-amber-400">
            {val(inverter.current_power_w, 'W', 0)}
          </div>
        </div>

        <div className="rounded-xl bg-slate-100 dark:bg-slate-800/80 p-3">
          <div className="text-xs text-slate-500 dark:text-slate-400">Daily Energy</div>
          <div className="mt-1 text-lg font-bold">{val(inverter.daily_energy_kwh, 'kWh')}</div>
        </div>

        <div className="rounded-xl bg-slate-100 dark:bg-slate-800/80 p-3">
          <div className="text-xs text-slate-500 dark:text-slate-400">Total Energy</div>
          <div className="mt-1 text-lg font-bold">{val(inverter.total_energy_kwh, 'kWh', 1)}</div>
        </div>

        <div className="rounded-xl bg-slate-100 dark:bg-slate-800/80 p-3">
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <Thermometer className="h-3.5 w-3.5" /> Temperature
          </div>
          <div className="mt-1 text-lg font-bold">{val(inverter.temperature_c, '°C', 1)}</div>
        </div>
      </div>

      {/* AC Electrical Parameters */}
      <div className="grid grid-cols-3 gap-3 text-xs border-y border-slate-100 dark:border-slate-800 py-3">
        <div>
          <span className="text-slate-500 dark:text-slate-400 block">AC Voltage</span>
          <span className="font-mono font-semibold text-sm">{val(inverter.ac_voltage_v, 'V', 1)}</span>
        </div>
        <div>
          <span className="text-slate-500 dark:text-slate-400 block">AC Current</span>
          <span className="font-mono font-semibold text-sm">{val(inverter.ac_current_a, 'A', 2)}</span>
        </div>
        <div>
          <span className="text-slate-500 dark:text-slate-400 block">Grid Frequency</span>
          <span className="font-mono font-semibold text-sm">{val(inverter.ac_frequency_hz, 'Hz', 2)}</span>
        </div>
      </div>

      {/* PV1..PV4 Inputs */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Individual PV Inputs (PV1–PV4)
          </h4>
          <span className="text-[11px] text-slate-400">
            Measured values only — never estimated
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {inverter.pv_inputs.map((pv) => (
            <PvInputCard key={pv.channel} pv={pv} />
          ))}
        </div>
      </div>
    </article>
  );
}
