import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import DashboardOverview from './components/DashboardOverview';
import SingleTaskRun from './components/SingleTaskRun';
import BatchBenchmark from './components/BatchBenchmark';
import RunsTable from './components/RunsTable';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import ComparisonsAndStats from './components/ComparisonsAndStats';
import ICoderReference from './components/ICoderReference';
import RunVisualizer from './components/RunVisualizer';
import SettingsView from './components/SettingsView';

export default function App() {
  const [initialPath] = useState(() => window.location.pathname);
  const matchedRunId = initialPath.match(/\/runs\/([^/]+)/)?.[1] || '';

  const [activeTab, setActiveTab] = useState(() => (matchedRunId ? 'visualizer' : 'dashboard'));
  const [currentRunId, setCurrentRunId] = useState(matchedRunId);

  const [runs, setRuns] = useState([]);
  const [summary, setSummary] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [resRuns, resAnalytics] = await Promise.all([
        fetch('/api/runs?limit=100').then((r) => (r.ok ? r.json() : null)),
        fetch('/api/analytics/summary').then((r) => (r.ok ? r.json() : null)),
      ]);

      if (resRuns) {
        setRuns(resRuns.runs || []);
        setSummary(resRuns.summary || null);
      }
      if (resAnalytics) {
        setAnalyticsData(resAnalytics);
      }
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // 15s polling for background updates
    return () => clearInterval(interval);
  }, [fetchData]);

  // Handle run selection
  const handleSelectRun = (runId) => {
    setCurrentRunId(runId);
    setActiveTab('visualizer');
    window.history.pushState({}, '', `/runs/${runId}`);
  };

  const handleRunCreated = (newRunId) => {
    fetchData();
    handleSelectRun(newRunId);
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'dashboard') {
      window.history.pushState({}, '', '/');
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        currentRunId={currentRunId}
      />

      {/* Main Content Pane */}
      <main className="flex-1 p-6 md:p-8 overflow-y-auto max-w-7xl">
        {activeTab === 'dashboard' && (
          <DashboardOverview
            summary={summary}
            recentRuns={runs}
            onNavigate={handleTabChange}
            onSelectRun={handleSelectRun}
          />
        )}

        {activeTab === 'single_run' && (
          <SingleTaskRun onRunCreated={handleRunCreated} />
        )}

        {activeTab === 'batch' && (
          <BatchBenchmark onNavigate={handleTabChange} />
        )}

        {activeTab === 'runs' && (
          <RunsTable runs={runs} onSelectRun={handleSelectRun} />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsDashboard runs={runs} analyticsData={analyticsData} />
        )}

        {activeTab === 'comparisons' && (
          <ComparisonsAndStats analyticsData={analyticsData} />
        )}

        {activeTab === 'icoder' && (
          <ICoderReference analyticsData={analyticsData} />
        )}

        {activeTab === 'visualizer' && (
          <RunVisualizer
            runId={currentRunId}
            onRunIdChange={(newId) => {
              setCurrentRunId(newId);
              window.history.pushState({}, '', `/runs/${newId}`);
            }}
          />
        )}

        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  );
}
