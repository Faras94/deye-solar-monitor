import { useEffect, useState } from 'react';
import { Radar, Save, AlertCircle, CheckCircle2, HelpCircle } from 'lucide-react';
import { solarApi } from '../api/client';
import type { AvailablePoint, Device, MeasurementMapping } from '../types/solar';

export function DeviceManagementView() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [mappings, setMappings] = useState<MeasurementMapping[]>([]);
  const [unmapped, setUnmapped] = useState<AvailablePoint[]>([]);
  const [available, setAvailable] = useState<AvailablePoint[]>([]);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [devs, mapRes] = await Promise.all([solarApi.getDevices(), solarApi.getMappings()]);
      setDevices(devs);
      setMappings(mapRes.mappings);
      setUnmapped(mapRes.unmapped_points);
      setAvailable(mapRes.available_points);
      const draft: Record<string, string> = {};
      for (const m of mapRes.mappings) {
        draft[m.dashboard_field] = m.deye_key ?? '';
      }
      setDraftKeys(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load device configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleDiscover = async () => {
    setDiscovering(true);
    setError(null);
    setNotice(null);
    try {
      const res = await solarApi.discoverDevices();
      setNotice(res.message);
      if (res.errors.length > 0) {
        setError(res.errors.join(' | '));
      }
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSaveMappings = async () => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload = mappings.map((m) => ({
        dashboard_field: m.dashboard_field,
        deye_key: draftKeys[m.dashboard_field]?.trim() || null,
      }));
      const updated = await solarApi.saveMappings(payload);
      setMappings(updated.mappings);
      setUnmapped(updated.unmapped_points);
      setAvailable(updated.available_points);
      setNotice('Measurement mappings saved. Live dashboard values will reflect updated keys.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save mappings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-sm text-slate-500">
        Loading devices and measurement mappings...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {notice && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 px-4 py-3 text-sm flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 px-4 py-3 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Configured Devices */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-base">Configured Microinverters</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Discover station bindings and supported DeyeCloud measurement points.
            </p>
          </div>
          <button
            type="button"
            onClick={handleDiscover}
            disabled={discovering}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white text-sm font-medium transition"
          >
            <Radar className="h-4 w-4" />
            {discovering ? 'Discovering...' : 'Discover Devices & Points'}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {devices.map((dev) => (
            <div
              key={dev.device_sn}
              className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm">{dev.name}</span>
                <span className="text-xs uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800">
                  {dev.status}
                </span>
              </div>
              <div className="text-xs font-mono text-slate-500 dark:text-slate-400">
                SN: {dev.device_sn}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Type: {dev.device_type} • Station ID: {dev.station_id ?? 'Not bound'}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Discovered Points: {dev.available_points.length}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Mapping Configuration + Unmapped Points */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-base">Measurement Field Mappings</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Map actual DeyeCloud measurement identifiers to dashboard fields.
              </p>
            </div>
            <button
              type="button"
              onClick={handleSaveMappings}
              disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-medium transition"
            >
              <Save className="h-4 w-4" />
              {saving ? 'Saving...' : 'Save Mappings'}
            </button>
          </div>

          <datalist id="deye-available-keys">
            {available.map((pt) => (
              <option key={pt.key} value={pt.key}>
                {pt.name ? `${pt.name} (${pt.unit || ''})` : pt.key}
              </option>
            ))}
          </datalist>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <th className="py-2 pr-3">Dashboard Field</th>
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2">DeyeCloud Key</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {mappings.map((m) => (
                  <tr key={m.dashboard_field}>
                    <td className="py-2 pr-3">
                      <div className="font-medium">{m.label}</div>
                      <div className="text-[11px] font-mono text-slate-400">
                        {m.dashboard_field} {m.unit ? `(${m.unit})` : ''}
                      </div>
                    </td>
                    <td className="py-2 pr-3">
                      <span className="text-xs uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
                        {m.category}
                      </span>
                    </td>
                    <td className="py-2">
                      <input
                        type="text"
                        list="deye-available-keys"
                        value={draftKeys[m.dashboard_field] ?? ''}
                        onChange={(e) =>
                          setDraftKeys((prev) => ({ ...prev, [m.dashboard_field]: e.target.value }))
                        }
                        placeholder="Enter DeyeCloud key..."
                        className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 font-mono text-xs"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Unmapped Measurement Points */}
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4 text-amber-500" />
            <h2 className="font-semibold text-base">Unmapped Points ({unmapped.length})</h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Measurement keys returned by DeyeCloud that are not currently assigned to any dashboard field.
          </p>

          {unmapped.length === 0 ? (
            <div className="text-xs text-slate-400 py-6 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              No unmapped measurement points discovered yet. Run &ldquo;Discover Devices &amp; Points&rdquo; or refresh live data.
            </div>
          ) : (
            <ul className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
              {unmapped.map((pt) => (
                <li
                  key={pt.key}
                  className="rounded-xl border border-slate-200 dark:border-slate-800 p-2.5 text-xs"
                >
                  <div className="font-mono font-semibold text-amber-600 dark:text-amber-400">
                    {pt.key}
                  </div>
                  <div className="text-slate-500 dark:text-slate-400 mt-0.5">
                    {pt.name || 'Unnamed point'} {pt.unit ? `• Unit: ${pt.unit}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
