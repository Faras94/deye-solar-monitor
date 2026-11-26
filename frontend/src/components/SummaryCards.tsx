import { Zap, BatteryCharging, Calendar, Award, Wifi } from 'lucide-react';
import type { LiveSummary } from '../types/solar';

function fmt(value: number | null | undefined, suffix: string, decimals = 2): string {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(decimals)} ${suffix}`;
}

export function SummaryCards({ summary }: { summary: LiveSummary }) {
  const cards = [
    {
      label: 'Total Current Power',
      value: summary.total_current_power_w !== null ? `${summary.total_current_power_w.toFixed(0)} W` : 'N/A',
      sub: 'Combined live AC output',
      icon: Zap,
      accent: 'text-amber-500 bg-amber-500/10',
    },
    {
      label: 'Daily Generation',
      value: fmt(summary.total_daily_energy_kwh, 'kWh'),
      sub: 'Today across all inverters',
      icon: BatteryCharging,
      accent: 'text-emerald-500 bg-emerald-500/10',
    },
    {
      label: 'Monthly Generation',
      value: fmt(summary.total_monthly_energy_kwh, 'kWh'),
      sub: 'Current month (if reported)',
      icon: Calendar,
      accent: 'text-sky-500 bg-sky-500/10',
    },
    {
      label: 'Lifetime Generation',
      value: fmt(summary.total_lifetime_energy_kwh, 'kWh', 1),
      sub: 'Cumulative total (if reported)',
      icon: Award,
      accent: 'text-violet-500 bg-violet-500/10',
    },
    {
      label: 'Inverter Fleet Status',
      value: `${summary.online_count} / ${summary.total_devices}`,
      sub: summary.offline_count > 0 ? `${summary.offline_count} offline / alert` : 'All inverters online',
      icon: Wifi,
      accent:
        summary.offline_count > 0
          ? 'text-rose-500 bg-rose-500/10'
          : 'text-emerald-500 bg-emerald-500/10',
    },
  ];

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {card.label}
              </span>
              <span className={`p-2 rounded-lg ${card.accent}`}>
                <Icon className="h-4 w-4" />
              </span>
            </div>
            <div className="mt-2 text-2xl font-bold tracking-tight">{card.value}</div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{card.sub}</div>
          </div>
        );
      })}
    </section>
  );
}
