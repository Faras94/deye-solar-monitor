import type { PVChannelReading } from '../types/solar';

function metric(value: number | null, unit: string): string {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(1)} ${unit}`;
}

export function PvInputCard({ pv }: { pv: PVChannelReading }) {
  const hasAny = pv.voltage !== null || pv.current !== null || pv.power !== null;

  return (
    <div
      className={`rounded-xl border p-3 transition ${
        hasAny
          ? 'border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800/60'
          : 'border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-900/40 opacity-75'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">
          PV{pv.channel}
        </span>
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
            hasAny
              ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
              : 'bg-slate-200 dark:bg-slate-800 text-slate-500'
          }`}
        >
          {hasAny ? 'Reported' : 'Unavailable'}
        </span>
      </div>

      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Voltage</span>
          <span className="font-mono font-medium">{metric(pv.voltage, pv.voltage_unit || 'V')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Current</span>
          <span className="font-mono font-medium">{metric(pv.current, pv.current_unit || 'A')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Power</span>
          <span className="font-mono font-semibold text-amber-600 dark:text-amber-400">
            {metric(pv.power, pv.power_unit || 'W')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500 dark:text-slate-400">Energy</span>
          <span className="font-mono font-medium text-emerald-600 dark:text-emerald-400">
            {pv.energy !== null && pv.energy !== undefined
              ? `${pv.energy.toFixed(2)} ${pv.energy_unit || 'kWh'}`
              : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
