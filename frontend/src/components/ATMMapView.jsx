import React, { useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { MapPin, Navigation, TrendingUp, ShieldAlert, CheckCircle2 } from 'lucide-react';

function ChangeMapView({ center, zoom }) {
  const map = useMap();
  map.setView(center, zoom);
  return null;
}

export default function ATMMapView({ atms, onSelectAtm }) {
  const [activeCity, setActiveCity] = useState('All');
  const [riskFilter, setRiskFilter] = useState('All');

  // Centers
  const cityConfigs = {
    All: { center: [57.8, 34.0], zoom: 6 },
    Moscow: { center: [55.7558, 37.6173], zoom: 11 },
    'Saint Petersburg': { center: [59.9343, 30.3351], zoom: 11 },
  };

  const filteredAtms = atms.filter((atm) => {
    const matchCity = activeCity === 'All' || atm.city === activeCity;
    const matchRisk = riskFilter === 'All' || atm.risk_level.toLowerCase() === riskFilter.toLowerCase();
    return matchCity && matchRisk;
  });

  const getMarkerColor = (risk) => {
    switch (risk?.toLowerCase()) {
      case 'high':
        return '#EF4444';
      case 'medium':
        return '#F59E0B';
      default:
        return '#10B981';
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl border border-gray-800 flex flex-col h-[560px]">
      {/* Map Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
            <MapPin className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">
              Fleet Geographic Intelligence
            </h2>
            <p className="text-xs text-gray-400">
              Interactive Leaflet GIS across Moscow & Saint Petersburg
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-2">
          {/* City Toggle */}
          <div className="flex bg-gray-900/90 rounded-lg p-1 border border-gray-800 text-xs">
            {['All', 'Moscow', 'Saint Petersburg'].map((city) => (
              <button
                key={city}
                onClick={() => setActiveCity(city)}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  activeCity === city
                    ? 'bg-[#FFDD2D] text-black font-semibold shadow-sm'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {city === 'Saint Petersburg' ? 'SPb' : city}
              </button>
            ))}
          </div>

          {/* Risk Level Filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="bg-gray-900 border border-gray-800 text-xs text-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-yellow-400"
          >
            <option value="All">All Risk Levels</option>
            <option value="High">🔴 High Risk Only</option>
            <option value="Medium">🟠 Medium Risk</option>
            <option value="Low">🟢 Low Risk / Safe</option>
          </select>
        </div>
      </div>

      {/* Leaflet Map Container */}
      <div className="flex-1 w-full rounded-xl overflow-hidden border border-gray-800 relative">
        <MapContainer
          center={cityConfigs[activeCity].center}
          zoom={cityConfigs[activeCity].zoom}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
        >
          <ChangeMapView
            center={cityConfigs[activeCity].center}
            zoom={cityConfigs[activeCity].zoom}
          />
          {/* CartoDB Dark Matter Tiles for Sleek Financial Dashboard Look */}
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          />

          {filteredAtms.map((atm) => {
            const color = getMarkerColor(atm.risk_level);
            return (
              <CircleMarker
                key={atm.atm_id}
                center={[atm.latitude, atm.longitude]}
                radius={atm.risk_level?.toLowerCase() === 'high' ? 10 : 8}
                pathOptions={{
                  color: color,
                  fillColor: color,
                  fillOpacity: 0.85,
                  weight: 2,
                }}
              >
                <Popup>
                  <div className="p-1 min-w-[220px]">
                    <div className="flex items-center justify-between border-b border-gray-700 pb-2 mb-2">
                      <span className="font-bold text-sm text-white">
                        {atm.atm_name}
                      </span>
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          atm.risk_level?.toLowerCase() === 'high'
                            ? 'bg-red-500/20 text-red-400'
                            : atm.risk_level?.toLowerCase() === 'medium'
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-emerald-500/20 text-emerald-400'
                        }`}
                      >
                        {atm.risk_level} Risk
                      </span>
                    </div>

                    <p className="text-xs text-gray-300 mb-1">
                      <span className="text-gray-400">Location:</span> {atm.address}
                    </p>
                    <p className="text-xs text-gray-300 mb-2">
                      <span className="text-gray-400">Type:</span> {atm.location_type}
                    </p>

                    <div className="bg-gray-800/80 p-2 rounded-lg mb-3">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-400">Current Cash:</span>
                        <span className="font-bold text-yellow-300">
                          {atm.current_cash?.toLocaleString()} units
                        </span>
                      </div>
                      <div className="flex justify-between text-[11px] text-gray-400">
                        <span>Min Safety Stock:</span>
                        <span>{atm.min_safety_stock?.toLocaleString()} units</span>
                      </div>
                      <div className="w-full bg-gray-700 h-1.5 rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full bg-yellow-400"
                          style={{
                            width: `${Math.min(
                              100,
                              atm.capacity_utilization_pct || 0
                            )}%`,
                          }}
                        />
                      </div>
                    </div>

                    <button
                      onClick={() => onSelectAtm(atm.atm_id)}
                      className="w-full text-xs font-semibold bg-[#FFDD2D] hover:bg-[#e6c518] text-black py-1.5 px-3 rounded-lg transition flex items-center justify-center gap-1.5"
                    >
                      <TrendingUp className="w-3.5 h-3.5" />
                      <span>Forecast Demand & Risks</span>
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
