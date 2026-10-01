import React from 'react';
import { DollarSign, TrendingDown, AlertTriangle, Truck, Activity, ShieldCheck } from 'lucide-react';

export default function KPICards({ summary, loading }) {
  if (loading || !summary) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="glass-panel p-4 h-28 animate-pulse bg-gray-800/40 rounded-xl" />
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: 'Total Network Cash',
      value: `${summary.total_cash_in_network?.toLocaleString()} units`,
      sub: `${summary.network_utilization_pct}% of total capacity`,
      icon: DollarSign,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      title: '24h Demand Forecast',
      value: `${summary.forecasted_24h_network_demand?.toLocaleString()} units`,
      sub: `Across ${summary.total_atms} active terminals`,
      icon: TrendingDown,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/20',
    },
    {
      title: 'High-Risk Terminals',
      value: summary.high_risk_atms_count || 0,
      sub: `${summary.medium_risk_atms_count || 0} at medium risk buffer`,
      icon: AlertTriangle,
      color: summary.high_risk_atms_count > 0 ? 'text-red-400' : 'text-emerald-400',
      bg: summary.high_risk_atms_count > 0 ? 'bg-red-500/10' : 'bg-emerald-500/10',
      border: summary.high_risk_atms_count > 0 ? 'border-red-500/30' : 'border-emerald-500/20',
    },
    {
      title: 'Pending Refill Orders',
      value: summary.pending_refill_orders || 0,
      sub: 'CIT Armored Vans Required',
      icon: Truck,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
    },
    {
      title: 'Replenishment Volume',
      value: `${summary.total_replenishment_needed?.toLocaleString()} units`,
      sub: `~${((summary.total_replenishment_needed || 0) * 34).toLocaleString()} ₽ (Base est.)`,
      icon: Activity,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/20',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      {cards.map((c, idx) => {
        const Icon = c.icon;
        return (
          <div
            key={idx}
            className={`glass-panel p-4.5 rounded-xl border ${c.border} transition hover:translate-y-[-2px] hover:shadow-lg`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-400 tracking-wide uppercase">
                {c.title}
              </span>
              <div className={`p-2 rounded-lg ${c.bg} ${c.color}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div className="text-xl font-bold text-white tracking-tight mb-1">
              {c.value}
            </div>
            <div className="text-[11px] text-gray-400 font-medium">
              {c.sub}
            </div>
          </div>
        );
      })}
    </div>
  );
}
