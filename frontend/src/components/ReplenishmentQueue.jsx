import React, { useState } from 'react';
import { Truck, CheckCircle2, AlertOctagon, ArrowUpRight, Search, ShieldCheck } from 'lucide-react';
import api from '../services/api';

export default function ReplenishmentQueue({ queue, currentUser, onRefreshQueue, onSelectAtm }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('All');
  const [approvingId, setApprovingId] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);

  const canApprove =
    currentUser && (currentUser.role === 'admin' || currentUser.role === 'operations_manager');

  const filteredQueue = queue.filter((item) => {
    const matchSearch =
      item.atm_id.toString().includes(searchTerm) ||
      item.atm_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.city.toLowerCase().includes(searchTerm.toLowerCase());

    const matchPriority =
      priorityFilter === 'All' ||
      item.priority.toLowerCase().includes(priorityFilter.toLowerCase());

    return matchSearch && matchPriority;
  });

  const handleApprove = async (item) => {
    setApprovingId(item.atm_id);
    try {
      const res = await api.approveReplenishment(item.atm_id, item.recommended_refill);
      setSuccessNotice(`Armored Van dispatched for ATM #${item.atm_id}! Refill: ${item.recommended_refill} units.`);
      setTimeout(() => setSuccessNotice(null), 5000);
      onRefreshQueue();
    } catch (err) {
      alert(err.response?.data?.detail || 'Approval failed. Please check permissions.');
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl border border-gray-800">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-lg bg-yellow-500/10 text-[#FFDD2D]">
            <Truck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">
              CIT Replenishment Dispatch Queue
            </h2>
            <p className="text-xs text-gray-400">
              Formula: Refill = max(0, Forecast Demand + Safety Stock - Current Cash)
            </p>
          </div>
        </div>

        {/* Search & Filter */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search ATM..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-gray-900 border border-gray-800 text-xs text-gray-200 rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-yellow-400 w-36 sm:w-48"
            />
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-gray-900 border border-gray-800 text-xs text-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-yellow-400"
          >
            <option value="All">All Priorities</option>
            <option value="Urgent">🚨 Urgent (Priority 1)</option>
            <option value="Scheduled">⚠️ Scheduled (Priority 2)</option>
            <option value="Normal">✓ Normal (Priority 3)</option>
          </select>
        </div>
      </div>

      {/* Success Notification Alert */}
      {successNotice && (
        <div className="mb-4 p-3 bg-emerald-500/15 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs flex items-center justify-between animate-fade-in">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{successNotice}</span>
          </div>
        </div>
      )}

      {/* Queue Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-xs text-left text-gray-300">
          <thead className="bg-gray-800/80 text-gray-400 uppercase font-semibold">
            <tr>
              <th className="py-3 px-4">Priority / Score</th>
              <th className="py-3 px-4">Terminal</th>
              <th className="py-3 px-4">City</th>
              <th className="py-3 px-4 text-right">Current Cash</th>
              <th className="py-3 px-4 text-right">3d Forecast</th>
              <th className="py-3 px-4 text-right">Safety Buffer</th>
              <th className="py-3 px-4 text-right">Recommended Refill</th>
              <th className="py-3 px-4 text-center">CIT Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {filteredQueue.length === 0 ? (
              <tr>
                <td colSpan="8" className="py-8 text-center text-gray-500">
                  No terminals match current queue filters.
                </td>
              </tr>
            ) : (
              filteredQueue.map((item) => {
                const isUrgent = item.priority.includes('Urgent');
                const isScheduled = item.priority.includes('Scheduled');

                return (
                  <tr
                    key={item.atm_id}
                    className={`hover:bg-gray-800/50 transition ${
                      isUrgent ? 'bg-red-500/5' : ''
                    }`}
                  >
                    {/* Urgency */}
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            isUrgent
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : isScheduled
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}
                        >
                          Score {item.urgency_score}
                        </span>
                      </div>
                    </td>

                    {/* ATM ID */}
                    <td className="py-3 px-4">
                      <button
                        onClick={() => onSelectAtm(item.atm_id)}
                        className="font-bold text-white hover:text-[#FFDD2D] transition text-left flex items-center gap-1"
                      >
                        <span>{item.atm_name}</span>
                        <ArrowUpRight className="w-3 h-3 text-gray-400" />
                      </button>
                      <span className="text-[11px] text-gray-500">
                        {item.location_type}
                      </span>
                    </td>

                    {/* City */}
                    <td className="py-3 px-4 text-gray-300">{item.city}</td>

                    {/* Current Cash */}
                    <td className="py-3 px-4 text-right font-mono font-medium text-gray-200">
                      {item.current_cash?.toLocaleString()}
                    </td>

                    {/* Forecast */}
                    <td className="py-3 px-4 text-right font-mono text-gray-300">
                      {item.forecasted_demand?.toLocaleString()}
                    </td>

                    {/* Safety Stock */}
                    <td className="py-3 px-4 text-right font-mono text-gray-400">
                      {item.min_safety_stock?.toLocaleString()}
                    </td>

                    {/* Recommended Refill */}
                    <td className="py-3 px-4 text-right">
                      {item.recommended_refill > 0 ? (
                        <div>
                          <span className="font-bold text-[#FFDD2D] text-sm">
                            +{item.recommended_refill?.toLocaleString()}
                          </span>
                          <p className="text-[10px] text-gray-400">
                            ~{(item.recommended_refill * 34).toLocaleString(undefined, { maximumFractionDigits: 0 })} ₽
                          </p>
                        </div>
                      ) : (
                        <span className="text-gray-500 font-medium">Optimal (0)</span>
                      )}
                    </td>

                    {/* Action Button */}
                    <td className="py-3 px-4 text-center">
                      {item.recommended_refill > 0 ? (
                        <button
                          disabled={!canApprove || approvingId === item.atm_id}
                          onClick={() => handleApprove(item)}
                          className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition shadow-sm ${
                            canApprove
                              ? isUrgent
                                ? 'bg-red-600 hover:bg-red-500 text-white'
                                : 'bg-[#FFDD2D] hover:bg-[#e6c518] text-black'
                              : 'bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700'
                          }`}
                          title={
                            canApprove
                              ? 'Dispatch CIT armored van'
                              : 'Requires Operations Manager role'
                          }
                        >
                          {approvingId === item.atm_id ? (
                            'Dispatching...'
                          ) : (
                            <span>Dispatch CIT Van</span>
                          )}
                        </button>
                      ) : (
                        <span className="text-[11px] text-emerald-400 font-medium flex items-center justify-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Adequate</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
