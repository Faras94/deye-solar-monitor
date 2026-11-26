import { useEffect, useMemo, useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  Download,
  CalendarRange,
  AlertCircle,
  Zap,
  TrendingUp,
  Activity,
  Gauge,
  Leaf,
  IndianRupee,
  FileDown,
} from 'lucide-react';
import { solarApi } from '../api/client';
import type { HistoricalPoint } from '../types/solar';

const INVERTER_COLORS = ['#f59e0b', '#10b981', '#0ea5e9', '#8b5cf6'];

// Rated AC capacities (W) for the configured microinverters
const RATED_CAPACITY_W: Record<string, number> = {
  '260605A076': 2200,
  '260603A1D5': 2200,
  '260505A373': 1000,
};
const CO2_KG_PER_KWH = 0.82; // India CEA grid emission factor

type Granularity = 'intraday' | 'daily' | 'monthly' | 'yearly';
type DayBucketMode = 'raw' | 'hourly';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));

function inHourRange(periodKey: string, startHour: string, endHour: string): boolean {
  const hh = periodKey.slice(11, 13);
  if (!hh) return true;
  return hh >= startHour && hh <= endHour;
}

export function HistoryView({ configuredDevices }: { configuredDevices: string[] }) {
  const [granularity, setGranularity] = useState<Granularity>('intraday');
  const [dayBucketMode, setDayBucketMode] = useState<DayBucketMode>('hourly');
  const [selectedDay, setSelectedDay] = useState<string>(todayIso);
  const [startHour, setStartHour] = useState<string>('06');
  const [endHour, setEndHour] = useState<string>('19');
  const [startDate, setStartDate] = useState<string>(() => daysAgoIso(14));
  const [endDate, setEndDate] = useState<string>(todayIso);
  const [selectedInverter, setSelectedInverter] = useState<string>('ALL');
  const [tariffInr, setTariffInr] = useState<number>(7.5);
  const [records, setRecords] = useState<HistoricalPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchingRemote, setFetchingRemote] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const effectiveStart = granularity === 'intraday' ? selectedDay : startDate;
  const effectiveEnd = granularity === 'intraday' ? selectedDay : endDate;

  const loadHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await solarApi.getHistory({
        granularity,
        startDate: effectiveStart,
        endDate: effectiveEnd,
        deviceSn: selectedInverter === 'ALL' ? undefined : selectedInverter,
      });
      setRecords(res.records);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [granularity, effectiveStart, effectiveEnd, selectedInverter]);

  const handleFetchRemote = async () => {
    setFetchingRemote(true);
    setError(null);
    setMessage(null);
    try {
      const res = await solarApi.fetchHistory({
        start_date: effectiveStart,
        end_date: effectiveEnd,
        granularity,
      });
      setMessage(res.message);
      if (res.errors.length > 0) {
        setError(res.errors.join(' | '));
      }
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch history from DeyeCloud');
    } finally {
      setFetchingRemote(false);
    }
  };

  const filteredRecords = useMemo(() => {
    if (granularity !== 'intraday') return records;
    return records.filter((r) => inHourRange(r.period_key, startHour, endHour));
  }, [records, granularity, startHour, endHour]);

  const serialNumbers = useMemo(() => {
    if (selectedInverter !== 'ALL') return [selectedInverter];
    const set = new Set<string>(configuredDevices);
    for (const r of filteredRecords) set.add(r.device_sn);
    return Array.from(set);
  }, [configuredDevices, filteredRecords, selectedInverter]);

  const totalRatedKw = useMemo(() => {
    const sumW = serialNumbers.reduce((acc, sn) => acc + (RATED_CAPACITY_W[sn] ?? 2000), 0);
    return sumW / 1000;
  }, [serialNumbers]);

  const chartData = useMemo(() => {
    type ChartRow = Record<string, string | number> & {
      sortKey: string;
      period: string;
      total: number;
      cumulativeEnergy: number;
    };

    if (granularity === 'intraday' && dayBucketMode === 'hourly') {
      // Group into hourly buckets (HH:00) averaging power per inverter per hour
      const byHour: Record<
        string,
        {
          perSnSum: Record<string, number>;
          perSnCount: Record<string, number>;
          perSnEnergy: Record<string, number>;
        }
      > = {};

      for (const r of filteredRecords) {
        const hourKey = r.period_key.length >= 13 ? r.period_key.slice(0, 13) : r.period_key;
        if (!byHour[hourKey]) {
          byHour[hourKey] = { perSnSum: {}, perSnCount: {}, perSnEnergy: {} };
        }
        const p = r.power_w ?? 0;
        byHour[hourKey].perSnSum[r.device_sn] = (byHour[hourKey].perSnSum[r.device_sn] ?? 0) + p;
        byHour[hourKey].perSnCount[r.device_sn] =
          (byHour[hourKey].perSnCount[r.device_sn] ?? 0) + 1;
        if (r.energy_kwh !== null && r.energy_kwh !== undefined) {
          byHour[hourKey].perSnEnergy[r.device_sn] = Math.max(
            byHour[hourKey].perSnEnergy[r.device_sn] ?? 0,
            r.energy_kwh
          );
        }
      }

      const sortedHours: ChartRow[] = Object.entries(byHour)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([hourKey, data]) => {
          const hh = hourKey.slice(11, 13);
          const row: ChartRow = {
            sortKey: hourKey,
            period: `${hh}:00`,
            total: 0,
            cumulativeEnergy: 0,
          };
          for (const [sn, sum] of Object.entries(data.perSnSum)) {
            const avg = sum / (data.perSnCount[sn] || 1);
            row[sn] = Number(avg.toFixed(2));
            row.total = Number((row.total + avg).toFixed(2));
          }
          row.cumulativeEnergy = Number(
            Object.values(data.perSnEnergy)
              .reduce((a, b) => a + b, 0)
              .toFixed(3)
          );
          return row;
        });

      return sortedHours.map((row, idx) => {
        const windowSlice = sortedHours.slice(Math.max(0, idx - 2), idx + 1);
        const ma =
          windowSlice.reduce((sum, item) => sum + Number(item.total || 0), 0) /
          windowSlice.length;
        return { ...row, movingAvg: Number(ma.toFixed(2)) };
      });
    }

    const byPeriod: Record<string, ChartRow> = {};
    for (const r of filteredRecords) {
      const displayPeriod =
        granularity === 'intraday' && r.period_key.length >= 16
          ? r.period_key.slice(11, 16)
          : r.period_key;

      if (!byPeriod[r.period_key]) {
        byPeriod[r.period_key] = {
          sortKey: r.period_key,
          period: displayPeriod,
          total: 0,
          cumulativeEnergy: 0,
        };
      }
      const val = granularity === 'intraday' ? r.power_w ?? 0 : r.energy_kwh ?? 0;
      byPeriod[r.period_key][r.device_sn] = Number(val.toFixed(2));
      byPeriod[r.period_key].total = Number(
        ((byPeriod[r.period_key].total as number) + val).toFixed(2)
      );
      if (r.energy_kwh !== null && r.energy_kwh !== undefined) {
        byPeriod[r.period_key].cumulativeEnergy = Number(
          ((byPeriod[r.period_key].cumulativeEnergy as number) + r.energy_kwh).toFixed(3)
        );
      }
    }

    const sorted = Object.values(byPeriod).sort((a, b) =>
      String(a.sortKey).localeCompare(String(b.sortKey))
    );

    // Add 3-point moving average for trend visibility
    return sorted.map((row, idx) => {
      const windowSlice = sorted.slice(Math.max(0, idx - 2), idx + 1);
      const ma =
        windowSlice.reduce((sum, item) => sum + Number(item.total || 0), 0) /
        windowSlice.length;
      return { ...row, movingAvg: Number(ma.toFixed(2)) };
    });
  }, [filteredRecords, granularity, dayBucketMode]);

  // Hourly aggregation (for intraday) or period distribution
  const hourlyProfileData = useMemo(() => {
    if (granularity !== 'intraday') return [];
    const buckets: Record<string, { sum: number; count: number }> = {};
    for (const row of chartData) {
      const hour = String(row.period).slice(0, 2);
      if (!hour) continue;
      if (!buckets[hour]) buckets[hour] = { sum: 0, count: 0 };
      buckets[hour].sum += Number(row.total || 0);
      buckets[hour].count += 1;
    }
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([hour, info]) => ({
        hour: `${hour}:00`,
        avgPowerW: Number((info.sum / info.count).toFixed(1)),
      }));
  }, [chartData, granularity]);

  const stats = useMemo(() => {
    if (chartData.length === 0) {
      return {
        totalEnergyKwh: 0,
        peakValue: 0,
        peakTime: '—',
        avgValue: 0,
        specificYield: 0,
        capacityFactorPct: 0,
        savingsInr: 0,
        co2Kg: 0,
        points: 0,
      };
    }

    const totals = chartData.map((d) => Number(d.total || 0));
    const maxVal = Math.max(...totals);
    const peakRow = chartData.find((d) => Number(d.total || 0) === maxVal);
    const avgVal = totals.reduce((a, b) => a + b, 0) / totals.length;

    let totalEnergyKwh = 0;
    if (granularity === 'intraday') {
      const latestBySn: Record<string, number> = {};
      for (const r of filteredRecords) {
        if (r.energy_kwh !== null && r.energy_kwh !== undefined) {
          latestBySn[r.device_sn] = Math.max(latestBySn[r.device_sn] ?? 0, r.energy_kwh);
        }
      }
      totalEnergyKwh = Object.values(latestBySn).reduce((a, b) => a + b, 0);
    } else {
      totalEnergyKwh = totals.reduce((a, b) => a + b, 0);
    }

    const specificYield = totalRatedKw > 0 ? totalEnergyKwh / totalRatedKw : 0;
    const capacityFactorPct =
      granularity === 'intraday'
        ? totalRatedKw > 0
          ? (avgVal / (totalRatedKw * 1000)) * 100
          : 0
        : totalRatedKw > 0 && chartData.length > 0
        ? (totalEnergyKwh / (totalRatedKw * 24 * chartData.length)) * 100
        : 0;

    return {
      totalEnergyKwh,
      peakValue: maxVal,
      peakTime: peakRow ? String(peakRow.period) : '—',
      avgValue: avgVal,
      specificYield,
      capacityFactorPct,
      savingsInr: totalEnergyKwh * tariffInr,
      co2Kg: totalEnergyKwh * CO2_KG_PER_KWH,
      points: chartData.length,
    };
  }, [chartData, filteredRecords, granularity, totalRatedKw, tariffInr]);

  const perInverterStats = useMemo(() => {
    const rawList = serialNumbers.map((sn) => {
      const rows = filteredRecords.filter((r) => r.device_sn === sn);
      const ratedW = RATED_CAPACITY_W[sn] ?? 2000;
      const powers = rows.map((r) => r.power_w).filter((v): v is number => v !== null);
      const energies = rows.map((r) => r.energy_kwh).filter((v): v is number => v !== null);
      const peakW = powers.length ? Math.max(...powers) : null;
      const avgW = powers.length ? powers.reduce((a, b) => a + b, 0) / powers.length : null;
      const energyKwh =
        granularity === 'intraday'
          ? energies.length
            ? Math.max(...energies)
            : null
          : energies.length
          ? energies.reduce((a, b) => a + b, 0)
          : null;
      const yieldPerKwp = energyKwh !== null ? energyKwh / (ratedW / 1000) : null;
      const cfPct =
        granularity === 'intraday' && avgW !== null
          ? (avgW / ratedW) * 100
          : energyKwh !== null && rows.length > 0
          ? (energyKwh / ((ratedW / 1000) * 24 * rows.length)) * 100
          : null;
      return { sn, ratedW, count: rows.length, peakW, avgW, energyKwh, yieldPerKwp, cfPct };
    });

    const sumEnergy = rawList.reduce((acc, r) => acc + (r.energyKwh ?? 0), 0);
    return rawList.map((r) => ({
      ...r,
      sharePct: sumEnergy > 0 && r.energyKwh !== null ? (r.energyKwh / sumEnergy) * 100 : 0,
      savingsInr: r.energyKwh !== null ? r.energyKwh * tariffInr : null,
    }));
  }, [serialNumbers, filteredRecords, granularity, tariffInr]);

  const sharePieData = useMemo(
    () =>
      perInverterStats
        .filter((r) => (r.energyKwh ?? 0) > 0)
        .map((r) => ({ name: r.sn, value: Number((r.energyKwh ?? 0).toFixed(2)) })),
    [perInverterStats]
  );

  const exportCsv = () => {
    const header = 'device_sn,granularity,period_key,power_w,energy_kwh\n';
    const rows = filteredRecords
      .map(
        (r) =>
          `${r.device_sn},${r.granularity},${r.period_key},${r.power_w ?? ''},${r.energy_kwh ?? ''}`
      )
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deye-solar-${granularity}-${effectiveStart}-to-${effectiveEnd}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const unitLabel = granularity === 'intraday' ? 'W' : 'kWh';

  return (
    <div className="space-y-6">
      {/* Filter & Controls */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              View Mode
            </label>
            <div className="inline-flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1">
              {(
                [
                  { key: 'intraday', label: 'Day (Time)' },
                  { key: 'daily', label: 'Daily' },
                  { key: 'monthly', label: 'Monthly' },
                  { key: 'yearly', label: 'Yearly' },
                ] as const
              ).map((g) => (
                <button
                  key={g.key}
                  type="button"
                  onClick={() => setGranularity(g.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                    granularity === g.key
                      ? 'bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-sm'
                      : 'text-slate-600 dark:text-slate-300'
                  }`}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          {granularity === 'intraday' ? (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                  Select Day
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="date"
                    value={selectedDay}
                    onChange={(e) => setSelectedDay(e.target.value)}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setSelectedDay(todayIso())}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Today
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedDay(daysAgoIso(1))}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Yesterday
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                  Hour Time Frame
                </label>
                <div className="flex flex-wrap items-center gap-1.5">
                  <select
                    value={startHour}
                    onChange={(e) => setStartHour(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm font-mono"
                    aria-label="Start hour"
                  >
                    {HOURS.map((h) => (
                      <option key={h} value={h}>
                        {h}:00
                      </option>
                    ))}
                  </select>
                  <span className="text-xs text-slate-400">to</span>
                  <select
                    value={endHour}
                    onChange={(e) => setEndHour(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm font-mono"
                    aria-label="End hour"
                  >
                    {HOURS.map((h) => (
                      <option key={h} value={h}>
                        {h}:59
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => {
                      setStartHour('00');
                      setEndHour('23');
                    }}
                    className="px-2 py-1.5 rounded-lg text-xs border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    24h
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setStartHour('06');
                      setEndHour('18');
                    }}
                    className="px-2 py-1.5 rounded-lg text-xs border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    06–18h
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const nowH = new Date().getHours();
                      setStartHour(String(Math.max(0, nowH - 2)).padStart(2, '0'));
                      setEndHour(String(nowH).padStart(2, '0'));
                    }}
                    className="px-2 py-1.5 rounded-lg text-xs border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Last 3h
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                  Resolution
                </label>
                <div className="inline-flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1">
                  <button
                    type="button"
                    onClick={() => setDayBucketMode('hourly')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                      dayBucketMode === 'hourly'
                        ? 'bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-sm'
                        : 'text-slate-600 dark:text-slate-300'
                    }`}
                  >
                    Hourly
                  </button>
                  <button
                    type="button"
                    onClick={() => setDayBucketMode('raw')}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                      dayBucketMode === 'raw'
                        ? 'bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-sm'
                        : 'text-slate-600 dark:text-slate-300'
                    }`}
                  >
                    5-Min
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              Inverter
            </label>
            <select
              value={selectedInverter}
              onChange={(e) => setSelectedInverter(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm font-mono"
            >
              <option value="ALL">All ({totalRatedKw.toFixed(1)} kWp)</option>
              {configuredDevices.map((sn) => (
                <option key={sn} value={sn}>
                  {sn}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              Tariff (₹/kWh)
            </label>
            <input
              type="number"
              step="0.5"
              min="0"
              value={tariffInr}
              onChange={(e) => setTariffInr(Math.max(0, Number(e.target.value) || 0))}
              className="w-24 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-sm font-mono"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={exportCsv}
            disabled={filteredRecords.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 text-sm font-medium transition"
          >
            <FileDown className="h-4 w-4" />
            Export CSV
          </button>

          <button
            type="button"
            onClick={handleFetchRemote}
            disabled={fetchingRemote}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white text-sm font-medium transition"
          >
            <Download className="h-4 w-4" />
            {fetchingRemote ? 'Fetching...' : 'Fetch from DeyeCloud'}
          </button>
        </div>
      </div>

      {/* Advanced Solar KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Total Energy</span>
            <Zap className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono">
            {stats.totalEnergyKwh.toFixed(2)} kWh
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">{stats.points} sample(s)</div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Specific Yield</span>
            <Gauge className="h-4 w-4 text-sky-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono">
            {stats.specificYield.toFixed(2)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            kWh / kWp ({totalRatedKw.toFixed(1)} kWp)
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Peak {granularity === 'intraday' ? 'Power' : 'Period'}</span>
            <TrendingUp className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono">
            {stats.peakValue.toFixed(granularity === 'intraday' ? 0 : 2)} {unitLabel}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">At {stats.peakTime}</div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Capacity Factor</span>
            <Activity className="h-4 w-4 text-violet-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono">
            {stats.capacityFactorPct.toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Avg: {stats.avgValue.toFixed(granularity === 'intraday' ? 0 : 2)} {unitLabel}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Est. Savings</span>
            <IndianRupee className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            ₹{stats.savingsInr.toFixed(1)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">@ ₹{tariffInr.toFixed(2)}/kWh</div>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>CO₂ Offset</span>
            <Leaf className="h-4 w-4 text-teal-500" />
          </div>
          <div className="mt-1.5 text-xl font-bold font-mono text-teal-600 dark:text-teal-400">
            {stats.co2Kg.toFixed(1)} kg
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Grid emissions avoided</div>
        </div>
      </div>

      {message && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 px-4 py-3 text-sm">
          {message}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 px-4 py-3 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-sm text-slate-500">
          Loading {granularity} analytics from SQLite...
        </div>
      ) : chartData.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-12 text-center space-y-2">
          <CalendarRange className="h-8 w-8 mx-auto text-slate-400" />
          <p className="font-medium">No {granularity} readings stored for this selection.</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Click &ldquo;Fetch from DeyeCloud&rdquo; to pull {granularity} data, or wait for 5-minute live collections.
          </p>
        </div>
      ) : (
        <>
          {/* Row 1: Primary Curve + Inverter Comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
              <h3 className="font-semibold mb-4">
                {granularity === 'intraday'
                  ? `Intraday Power Curve & 3-Point Trend (${selectedDay})`
                  : `Total ${granularity} Generation & Trend (kWh)`}
              </h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  {granularity === 'intraday' ? (
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} unit=" W" />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="total"
                        name="Total Power (W)"
                        stroke="#f59e0b"
                        fill="#f59e0b"
                        fillOpacity={0.22}
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="movingAvg"
                        name="Moving Avg (W)"
                        stroke="#0ea5e9"
                        strokeDasharray="4 4"
                        dot={false}
                        strokeWidth={2}
                      />
                    </AreaChart>
                  ) : (
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} unit=" kWh" />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="total" name="Total (kWh)" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  )}
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
              <h3 className="font-semibold mb-4">
                Individual Microinverter Comparison ({unitLabel})
              </h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} unit={` ${unitLabel}`} />
                    <Tooltip />
                    <Legend />
                    {serialNumbers.map((sn, idx) => (
                      <Line
                        key={sn}
                        type="monotone"
                        dataKey={sn}
                        name={sn}
                        stroke={INVERTER_COLORS[idx % INVERTER_COLORS.length]}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Row 2: Inverter Share Donut + Hourly Profile / Cumulative Energy */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
              <h3 className="font-semibold mb-4">Inverter Energy Contribution Share (kWh)</h3>
              {sharePieData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-xs text-slate-400">
                  No positive energy share recorded in this window.
                </div>
              ) : (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={sharePieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={3}
                        label={({ name, percent }) =>
                          `${name} (${(percent * 100).toFixed(0)}%)`
                        }
                      >
                        {sharePieData.map((entry, idx) => (
                          <Cell
                            key={entry.name}
                            fill={INVERTER_COLORS[idx % INVERTER_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
              <h3 className="font-semibold mb-4">
                {granularity === 'intraday'
                  ? 'Hourly Average Power Profile (W)'
                  : 'Cumulative Energy Trend (kWh)'}
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  {granularity === 'intraday' ? (
                    <BarChart data={hourlyProfileData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} unit=" W" />
                      <Tooltip />
                      <Bar
                        dataKey="avgPowerW"
                        name="Avg Power (W)"
                        fill="#10b981"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  ) : (
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} unit=" kWh" />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="movingAvg"
                        name="3-Period Moving Avg (kWh)"
                        stroke="#8b5cf6"
                        fill="#8b5cf6"
                        fillOpacity={0.2}
                        strokeWidth={2}
                      />
                    </AreaChart>
                  )}
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Per-Inverter Advanced Analytics Table */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5">
            <h3 className="font-semibold mb-3">Per-Inverter Performance &amp; Yield Analytics</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <th className="py-2 pr-4">Serial Number</th>
                    <th className="py-2 pr-4">Rated</th>
                    <th className="py-2 pr-4">Peak Power</th>
                    <th className="py-2 pr-4">Avg Power</th>
                    <th className="py-2 pr-4">Energy</th>
                    <th className="py-2 pr-4">Share</th>
                    <th className="py-2 pr-4">Yield (kWh/kWp)</th>
                    <th className="py-2 pr-4">Cap. Factor</th>
                    <th className="py-2">Savings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-xs">
                  {perInverterStats.map((row) => (
                    <tr key={row.sn}>
                      <td className="py-2.5 pr-4 font-semibold">{row.sn}</td>
                      <td className="py-2.5 pr-4 text-slate-500">{row.ratedW} W</td>
                      <td className="py-2.5 pr-4">
                        {row.peakW !== null ? `${row.peakW.toFixed(0)} W` : 'N/A'}
                      </td>
                      <td className="py-2.5 pr-4">
                        {row.avgW !== null ? `${row.avgW.toFixed(0)} W` : 'N/A'}
                      </td>
                      <td className="py-2.5 pr-4 text-emerald-600 dark:text-emerald-400 font-semibold">
                        {row.energyKwh !== null ? `${row.energyKwh.toFixed(2)} kWh` : 'N/A'}
                      </td>
                      <td className="py-2.5 pr-4">{row.sharePct.toFixed(1)}%</td>
                      <td className="py-2.5 pr-4">
                        {row.yieldPerKwp !== null ? row.yieldPerKwp.toFixed(2) : 'N/A'}
                      </td>
                      <td className="py-2.5 pr-4">
                        {row.cfPct !== null ? `${row.cfPct.toFixed(1)}%` : 'N/A'}
                      </td>
                      <td className="py-2.5">
                        {row.savingsInr !== null ? `₹${row.savingsInr.toFixed(1)}` : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
