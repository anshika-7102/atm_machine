import React, { useState } from 'react';
import { X, Lock, User, Key, Check } from 'lucide-react';
import api from '../services/api';

export default function LoginModal({ isOpen, onClose, onLoginSuccess }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      onLoginSuccess(res);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSelect = (u, p) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="glass-panel bg-[#111827] border border-gray-700 w-full max-w-md rounded-2xl p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-5">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#FFDD2D] text-black font-bold flex items-center justify-center">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">System Authentication</h3>
              <p className="text-xs text-gray-400">Tinkoff Fleet Management Portal</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">
            {error}
          </div>
        )}

        {/* 1-Click Role Presets */}
        <div className="mb-4">
          <label className="block text-[11px] uppercase font-semibold text-gray-400 mb-2">
            1-Click Demo Profiles
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Admin', user: 'admin', role: 'Operations Director' },
              { label: 'Manager', user: 'manager', role: 'CIT Dispatch' },
              { label: 'Analyst', user: 'analyst', role: 'Forecaster' },
            ].map((p) => (
              <button
                key={p.user}
                type="button"
                onClick={() => handleQuickSelect(p.user, 'password123')}
                className={`p-2 rounded-xl text-left border transition text-xs ${
                  username === p.user
                    ? 'border-yellow-400 bg-yellow-400/10 text-white'
                    : 'border-gray-800 bg-gray-900/60 text-gray-400 hover:border-gray-700'
                }`}
              >
                <div className="font-bold flex items-center justify-between">
                  <span>{p.label}</span>
                  {username === p.user && <Check className="w-3 h-3 text-yellow-400" />}
                </div>
                <div className="text-[10px] text-gray-500">{p.role}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1">Username</label>
            <div className="relative">
              <User className="w-4 h-4 text-gray-500 absolute left-3 top-3" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full bg-gray-900 border border-gray-800 rounded-xl pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-yellow-400"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1">Password</label>
            <div className="relative">
              <Key className="w-4 h-4 text-gray-500 absolute left-3 top-3" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-gray-900 border border-gray-800 rounded-xl pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-yellow-400"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#FFDD2D] hover:bg-[#e6c518] text-black font-bold py-2.5 rounded-xl transition shadow-md text-sm mt-2"
          >
            {loading ? 'Authenticating...' : 'Sign In to Dashboard'}
          </button>
        </form>
      </div>
    </div>
  );
}
