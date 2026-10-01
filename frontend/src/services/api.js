import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to inject JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // Authentication
  login: async (username, password) => {
    const res = await apiClient.post('/auth/login', { username, password });
    if (res.data.access_token) {
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('user', JSON.stringify(res.data));
    }
    return res.data;
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },

  getCurrentUser: () => {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  },

  getMe: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  // Dashboard & Fleet
  getDashboardSummary: async () => {
    const res = await apiClient.get('/dashboard/summary');
    return res.data;
  },

  getAtms: async () => {
    const res = await apiClient.get('/atms');
    return res.data;
  },

  getAtmDetail: async (atmId) => {
    const res = await apiClient.get(`/atms/${atmId}`);
    return res.data;
  },

  // Forecasting & ML
  getForecast: async (atmId, days = 7) => {
    const res = await apiClient.get(`/forecast/${atmId}?days=${days}`);
    return res.data;
  },

  // Risk & Replenishment
  getRisk: async (atmId, days = 3) => {
    const res = await apiClient.get(`/risk/${atmId}?days=${days}`);
    return res.data;
  },

  getReplenishmentQueue: async () => {
    const res = await apiClient.get('/replenishment/queue');
    return res.data;
  },

  approveReplenishment: async (atmId, approvedAmount, notes = 'Dispatched from Fleet Dashboard') => {
    const res = await apiClient.post('/replenishment/approve', {
      atm_id: atmId,
      approved_amount: approvedAmount,
      notes: notes,
    });
    return res.data;
  },

  // Alerts & Reports
  getAlerts: async () => {
    const res = await apiClient.get('/alerts');
    return res.data;
  },

  getReports: async () => {
    const res = await apiClient.get('/reports');
    return res.data;
  },
};

export default api;
