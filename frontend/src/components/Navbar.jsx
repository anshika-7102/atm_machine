import React from 'react';
import { ShieldCheck, User, LogOut, LogIn, ExternalLink, Cpu } from 'lucide-react';

export default function Navbar({ currentUser, onOpenLogin, onLogout }) {
  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-gray-800 bg-[#111827]/90 px-6 py-3.5 mb-6">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-[#FFDD2D] flex items-center justify-center font-black text-black text-xl shadow-lg shadow-[#FFDD2D]/20">
            T
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold tracking-tight text-white">
                ATM Cash Demand Predictor
              </h1>
              <span className="text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-yellow-400/10 text-[#FFDD2D] border border-yellow-400/30">
                Tinkoff Fleet
              </span>
            </div>
            <p className="text-xs text-gray-400 flex items-center gap-1.5">
              <Cpu className="w-3 h-3 text-emerald-400" />
              <span>XGBoost Multi-Step Regressor (MAE: 220.21 | 74.3% Acc)</span>
            </p>
          </div>
        </div>

        {/* Right Action Items */}
        <div className="flex items-center space-x-4">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="hidden md:flex items-center space-x-1.5 text-xs text-gray-300 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition"
          >
            <span>Swagger API</span>
            <ExternalLink className="w-3.5 h-3.5 text-gray-400" />
          </a>

          {/* User Profile / Login */}
          {currentUser ? (
            <div className="flex items-center space-x-3 bg-gray-800/80 px-3 py-1.5 rounded-xl border border-gray-700">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">
                {currentUser.username ? currentUser.username[0].toUpperCase() : 'U'}
              </div>
              <div className="text-left hidden sm:block">
                <p className="text-xs font-semibold text-gray-200 leading-tight">
                  {currentUser.username}
                </p>
                <p className="text-[10px] text-gray-400 capitalize">
                  {currentUser.role ? currentUser.role.replace('_', ' ') : 'User'}
                </p>
              </div>
              <button
                onClick={onLogout}
                title="Logout"
                className="text-gray-400 hover:text-red-400 transition p-1"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenLogin}
              className="flex items-center space-x-2 text-xs font-semibold bg-[#FFDD2D] hover:bg-[#e6c518] text-black px-4 py-2 rounded-xl transition shadow-sm font-medium"
            >
              <LogIn className="w-4 h-4" />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
