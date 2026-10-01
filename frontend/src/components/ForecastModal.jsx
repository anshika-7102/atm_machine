import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { X, Calendar, TrendingUp, AlertTriangle, ShieldCheck, DollarSign } from 'lucide-react';
import api from '../services/api';

export default function ForecastModal({ atmId, onClose }) {
  const [forecastData, setForecastData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [horizon, setHorizon] = useState(7);

  useEffect(() => {
    if (!atmId) return;
    const fetchData = async () => {
      setLoading(true);
      try {
        const [fc, rk] = await Promise.all([
          api.getForecast(atmId, horizon),
          api.getRisk(atmId, 3),
        ]);
        setForecastData(fc);
        setRiskData(rk);
      } catch (err) {
        setError('Failed to load forecast data from engine.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [atmId, horizon]);

  if (!atmId) return null;

  // Format data for Recharts
  const chartData = forecastData?.daily_forecasts?.map((item) => ({
    date: item.date,
    day_name: item.day_name.slice(0, 3),
    forecast: item.predicted_demand,
    lower: item.lower_bound_90pct,
    upper: item.upper_bound_90pct,
    uncertainty: [item.lower_bound_90pct, item.upper_bound_90pct],
  })) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="glass-panel bg-[#111827] border border-gray-700 w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-5">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-yellow-400/10 text-[#FFDD2D] border border-yellow-400/20">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                ATM #{atmId} Cash Demand Forecast
                {riskData && (
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
                      riskData.risk_level === 'High'
                        ? 'bg-red-500/20 text-red-400'
                        : riskData.risk_level === 'Medium'
                        ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-emerald-500/20 text-emerald-400'
                    }`}
                  >
                    {riskData.risk_level} Risk
                  </span>
                )}
              </h2>
              <p className="text-xs text-gray-400">
                Tuned XGBoost Regressor | Multi-day Recursive Forecast with 90% Confidence Interval
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="h-72 flex items-center justify-center text-gray-400 text-sm">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 rounded-full border-2 border-yellow-400 border-t-transparent animate-spin" />
              <span>Generating multi-step forecasts from XGBoost model...</span>
            </div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm">
            {error}
          </div>
        ) : (
          <div>
            {/* Risk & Balance Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
              <div className="bg-gray-800/60 p-3 rounded-xl border border-gray-700/60">
                <span className="text-[11px] text-gray-400 uppercase font-semibold">
                  Current Cash Balance
                </span>
                <p className="text-lg font-bold text-white mt-0.5">
                  {riskData?.current_cash?.toLocaleString()} units
                </p>
              </div>
              <div className="bg-gray-800/60 p-3 rounded-xl border border-gray-700/60">
                <span className="text-[11px] text-gray-400 uppercase font-semibold">
                  Safety Stock Buffer
                </span>
                <p className="text-lg font-bold text-gray-300 mt-0.5">
                  {riskData?.min_safety_stock?.toLocaleString()} units
                </p>
              </div>
              <div className="bg-gray-800/60 p-3 rounded-xl border border-gray-700/60">
                <span className="text-[11px] text-gray-400 uppercase font-semibold">
                  Stockout Probability
                </span>
                <p
                  className={`text-lg font-bold mt-0.5 ${
                    (riskData?.cash_out_probability || 0) > 0.5
                      ? 'text-red-400'
                      : 'text-emerald-400'
                  }`}
                >
                  {((riskData?.cash_out_probability || 0) * 100).toFixed(1)}%
                </p>
              </div>
              <div className="bg-gray-800/60 p-3 rounded-xl border border-gray-700/60">
                <span className="text-[11px] text-gray-400 uppercase font-semibold">
                  Days Until Empty
                </span>
                <p className="text-lg font-bold text-yellow-300 mt-0.5">
                  {riskData?.days_until_cashout !== null
                    ? `${riskData?.days_until_cashout} Days`
                    : 'Safe (>7d)'}
                </p>
              </div>
            </div>

            {/* Forecast Horizon Controls */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-200">
                Demand Outflow Trajectory ({horizon}-Day Window)
              </h3>
              <div className="flex items-center space-x-1.5 bg-gray-800 p-1 rounded-lg border border-gray-700 text-xs">
                {[3, 5, 7, 14].map((d) => (
                  <button
                    key={d}
                    onClick={() => setHorizon(d)}
                    className={`px-2.5 py-1 rounded font-medium transition ${
                      horizon === d
                        ? 'bg-[#FFDD2D] text-black font-bold'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {d}D
                  </button>
                ))}
              </div>
            </div>

            {/* Recharts Chart */}
            <div className="h-72 w-full bg-gray-900/60 p-3 rounded-xl border border-gray-800 mb-6">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                  <XAxis
                    dataKey="day_name"
                    stroke="#9CA3AF"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#9CA3AF"
                    fontSize={12}
                    tickLine={false}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      borderColor: '#4B5563',
                      borderRadius: '8px',
                      color: '#F9FAFB',
                    }}
                    formatter={(val, name) => [
                      `${Number(val).toLocaleString()} units`,
                      name === 'forecast'
                        ? 'Forecast Demand'
                        : name === 'upper'
                        ? 'Upper 90%'
                        : 'Lower 90%',
                    ]}
                  />
                  <Legend />
                  {/* Uncertainty Band */}
                  <Area
                    type="monotone"
                    dataKey="upper"
                    stroke="none"
                    fill="#FFDD2D"
                    fillOpacity={0.15}
                    name="90% Uncertainty Bound"
                  />
                  {/* Forecast Line */}
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke="#FFDD2D"
                    strokeWidth={3}
                    dot={{ fill: '#FFDD2D', r: 4 }}
                    activeDot={{ r: 6 }}
                    name="Predicted Demand"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Day by Day Forecast Table */}
            <h4 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-2">
              Forecast Detail Table
            </h4>
            <div className="overflow-x-auto rounded-xl border border-gray-800">
              <table className="w-full text-xs text-left text-gray-300">
                <thead className="bg-gray-800/80 text-gray-400 uppercase font-semibold">
                  <tr>
                    <th className="py-2.5 px-4">Day Ahead</th>
                    <th className="py-2.5 px-4">Date</th>
                    <th className="py-2.5 px-4">Day</th>
                    <th className="py-2.5 px-4 text-right">Forecast (Units)</th>
                    <th className="py-2.5 px-4 text-right">Estimated Rubles</th>
                    <th className="py-2.5 px-4 text-right">90% Range</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {forecastData?.daily_forecasts?.map((d) => (
                    <tr key={d.day_ahead} className="hover:bg-gray-800/40">
                      <td className="py-2.5 px-4 font-mono font-medium">+{d.day_ahead}d</td>
                      <td className="py-2.5 px-4">{d.date}</td>
                      <td className="py-2.5 px-4 font-semibold text-white">{d.day_name}</td>
                      <td className="py-2.5 px-4 text-right font-bold text-yellow-300">
                        {d.predicted_demand.toLocaleString()}
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-400">
                        {(d.predicted_demand * 34).toLocaleString(undefined, { maximumFractionDigits: 0 })} ₽
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-gray-400">
                        {d.lower_bound_90pct.toFixed(0)} - {d.upper_bound_90pct.toFixed(0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
