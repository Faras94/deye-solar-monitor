export interface AvailablePoint {
  key: string;
  name?: string | null;
  unit?: string | null;
}

export interface Device {
  device_sn: string;
  name: string;
  device_type: string;
  station_id?: number | null;
  status: 'online' | 'offline' | 'alert' | 'unknown' | string;
  collection_time?: string | null;
  last_seen_at?: string | null;
  available_points: AvailablePoint[];
}

export interface PVChannelReading {
  channel: number;
  voltage: number | null;
  current: number | null;
  power: number | null;
  energy?: number | null;
  voltage_unit?: string | null;
  current_unit?: string | null;
  power_unit?: string | null;
  energy_unit?: string | null;
}

export interface RawMeasurementPoint {
  key: string;
  value: string | number | null;
  unit?: string | null;
  name?: string | null;
}

export interface InverterLive {
  device_sn: string;
  name: string;
  status: string;
  collection_time?: string | null;
  last_seen_at?: string | null;
  rated_power_w?: number | null;
  current_power_w: number | null;
  daily_energy_kwh: number | null;
  monthly_energy_kwh: number | null;
  total_energy_kwh: number | null;
  ac_voltage_v: number | null;
  ac_current_a: number | null;
  ac_frequency_hz: number | null;
  temperature_c: number | null;
  pv_inputs: PVChannelReading[];
  raw_points: RawMeasurementPoint[];
}

export interface LiveSummary {
  total_current_power_w: number | null;
  total_daily_energy_kwh: number | null;
  total_monthly_energy_kwh: number | null;
  total_lifetime_energy_kwh: number | null;
  online_count: number;
  offline_count: number;
  total_devices: number;
}

export interface LiveDashboardResponse {
  summary: LiveSummary;
  inverters: InverterLive[];
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  last_error?: string | null;
}

export interface HealthResponse {
  status: string;
  database: string;
  credentials_configured: boolean;
  base_url: string;
  configured_devices: string[];
  poll_interval_minutes: number;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  last_error?: string | null;
}

export interface CollectResponse {
  status: string;
  message: string;
  devices_updated: number;
  synced_at: string;
  errors: string[];
}

export interface DiscoverResponse {
  status: string;
  message: string;
  discovered_devices: Device[];
  errors: string[];
}

export interface HistoricalPoint {
  device_sn: string;
  granularity: 'intraday' | 'daily' | 'monthly' | 'yearly';
  period_key: string;
  energy_kwh: number | null;
  power_w: number | null;
}

export interface HistoryQueryResponse {
  granularity: 'intraday' | 'daily' | 'monthly' | 'yearly';
  start_date?: string | null;
  end_date?: string | null;
  records: HistoricalPoint[];
}

export interface HistoryFetchResponse {
  status: string;
  message: string;
  records_saved: number;
  errors: string[];
}

export interface MeasurementMapping {
  dashboard_field: string;
  deye_key: string | null;
  label: string;
  unit?: string | null;
  category: string;
}

export interface MappingsListResponse {
  mappings: MeasurementMapping[];
  unmapped_points: AvailablePoint[];
  available_points: AvailablePoint[];
}

export interface SchedulerConfig {
  enabled: boolean;
  interval_minutes: number;
}

export interface ApiCallLog {
  id: number;
  method: string;
  endpoint: string;
  status_code?: number | null;
  success: boolean;
  duration_ms: number;
  error_message?: string | null;
  created_at: string;
}

export interface ApiEndpointCount {
  endpoint: string;
  total_calls: number;
  success_calls: number;
  error_calls: number;
  avg_duration_ms: number;
  last_called_at?: string | null;
}

export interface ApiUsageResponse {
  total_calls: number;
  calls_today: number;
  calls_this_month: number;
  calls_last_minute: number;
  monthly_quota: number;
  qpm_limit: number;
  success_calls: number;
  error_calls: number;
  endpoints: ApiEndpointCount[];
  recent_calls: ApiCallLog[];
}
