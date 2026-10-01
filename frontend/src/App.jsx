import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import KPICards from './components/KPICards';
import AlertsBanner from './components/AlertsBanner';
import ATMMapView from './components/ATMMapView';
import ReplenishmentQueue from './components/ReplenishmentQueue';
import ForecastModal from './components/ForecastModal';
import LoginModal from './components/LoginModal';
import api from './services/api';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [summary, setSummary] = useState(null);
  const [atms, setAtms] = useState([]);
  const [queue, setQueue] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAtmId, setSelectedAtmId] = useState(null);
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  // Initial load
  useEffect(() => {
    // Check saved session
    const savedUser = api.getCurrentUser();
    if (savedUser) {
      setCurrentUser(savedUser);
    }
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sumRes, atmsRes, queueRes, alertsRes] = await Promise.all([
        api.getDashboardSummary(),
        api.getAtms(),
        api.getReplenishmentQueue(),
        api.getAlerts(),
      ]);
      setSummary(sumRes);
      setAtms(atmsRes);
      setQueue(queueRes);
      setAlerts(alertsRes);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshQueue = async () => {
    try {
      const [q, s, a] = await Promise.all([
        api.getReplenishmentQueue(),
        api.getDashboardSummary(),
        api.getAlerts(),
      ]);
      setQueue(q);
      setSummary(s);
      setAlerts(a);
    } catch (err) {
      console.error('Failed refreshing queue:', err);
    }
  };

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 flex flex-col">
      {/* Top Navigation */}
      <Navbar
        currentUser={currentUser}
        onOpenLogin={() => setIsLoginOpen(true)}
        onLogout={handleLogout}
      />

      {/* Main Dashboard Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 pb-12">
        {/* Urgent Alerts Banner */}
        <AlertsBanner
          alerts={alerts}
          onSelectAtm={(id) => setSelectedAtmId(id)}
        />

        {/* Top-Level KPI Summary Cards */}
        <KPICards summary={summary} loading={loading} />

        {/* Geographic GIS Map */}
        <div className="mb-6">
          <ATMMapView
            atms={atms}
            onSelectAtm={(id) => setSelectedAtmId(id)}
          />
        </div>

        {/* Cash-In-Transit Replenishment Optimization Queue */}
        <div className="mb-6">
          <ReplenishmentQueue
            queue={queue}
            currentUser={currentUser}
            onRefreshQueue={handleRefreshQueue}
            onSelectAtm={(id) => setSelectedAtmId(id)}
          />
        </div>
      </main>

      {/* Demand Forecast Modal */}
      {selectedAtmId && (
        <ForecastModal
          atmId={selectedAtmId}
          onClose={() => setSelectedAtmId(null)}
        />
      )}

      {/* Authentication Modal */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
        onLoginSuccess={(user) => setCurrentUser(user)}
      />

      {/* Footer */}
      <footer className="border-t border-gray-800/80 py-4 text-center text-xs text-gray-500">
        ATM Cash Demand Predictor • Tinkoff Analytics Fleet Intelligence • Tuned XGBoost & Linear Programming CIT Optimizer
      </footer>
    </div>
  );
}
