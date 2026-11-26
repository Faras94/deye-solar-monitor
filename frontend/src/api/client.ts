import type {
  CollectResponse,
  Device,
  DiscoverResponse,
  HealthResponse,
  HistoryFetchResponse,
  HistoryQueryResponse,
  LiveDashboardResponse,
  MappingsListResponse,
  SchedulerConfig,
  ApiUsageResponse,
} from '../types/solar';

const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const solarApi = {
  getHealth: () => request<HealthResponse>('/health'),
  getDevices: () => request<Device[]>('/devices'),
  getLive: () => request<LiveDashboardResponse>('/live'),
  collectNow: () => request<CollectResponse>('/collect', { method: 'POST' }),
  discoverDevices: () => request<DiscoverResponse>('/discover', { method: 'POST' }),
  getHistory: (params: {
    granularity: 'intraday' | 'daily' | 'monthly' | 'yearly';
    startDate?: string;
    endDate?: string;
    deviceSn?: string;
  }) => {
    const qs = new URLSearchParams({ granularity: params.granularity });
    if (params.startDate) qs.set('start_date', params.startDate);
    if (params.endDate) qs.set('end_date', params.endDate);
    if (params.deviceSn) qs.set('device_sn', params.deviceSn);
    return request<HistoryQueryResponse>(`/history?${qs.toString()}`);
  },
  fetchHistory: (payload: {
    start_date: string;
    end_date: string;
    granularity: 'intraday' | 'daily' | 'monthly' | 'yearly';
    device_sns?: string[];
  }) =>
    request<HistoryFetchResponse>('/history/fetch', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getMappings: () => request<MappingsListResponse>('/mappings'),
  saveMappings: (mappings: Array<{ dashboard_field: string; deye_key: string | null }>) =>
    request<MappingsListResponse>('/mappings', {
      method: 'POST',
      body: JSON.stringify({ mappings }),
    }),
  getScheduler: () => request<SchedulerConfig>('/scheduler'),
  updateScheduler: (payload: SchedulerConfig) =>
    request<SchedulerConfig>('/scheduler', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getApiUsage: (limit = 100) => request<ApiUsageResponse>(`/usage?limit=${limit}`),
};
