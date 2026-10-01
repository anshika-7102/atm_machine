import React from 'react';
import { AlertTriangle, ArrowRight, ShieldAlert } from 'lucide-react';

export default function AlertsBanner({ alerts, onSelectAtm }) {
  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="mb-6 space-y-2">
      {alerts.slice(0, 3).map((alert) => (
        <div
          key={alert.alert_id}
          className="p-3.5 rounded-xl border border-red-500/40 bg-red-500/10 backdrop-blur-md flex items-center justify-between transition hover:border-red-500/60"
        >
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-red-500/20 text-red-400">
              <ShieldAlert className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold uppercase tracking-wider text-red-400">
                  {alert.severity} RISK
                </span>
                <span className="text-xs text-gray-400">•</span>
                <span className="text-xs font-bold text-white">
                  {alert.atm_name}
                </span>
              </div>
              <p className="text-xs text-gray-300 mt-0.5">
                {alert.message}
              </p>
            </div>
          </div>

          <button
            onClick={() => onSelectAtm(alert.atm_id)}
            className="flex items-center space-x-1 text-xs font-semibold text-red-300 hover:text-white bg-red-500/20 hover:bg-red-500/30 px-3 py-1.5 rounded-lg transition flex-shrink-0"
          >
            <span>Review & Refill</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
