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

// One URL per page, so pages can be bookmarked and the browser Back button works.
export const ROUTES = {
  overview: '/',
  generate: '/generate',
  benchmark: '/benchmark',
  runs: '/runs',
  run: '/runs/:id',
  charts: '/charts',
  compare: '/compare',
  paper: '/paper',
  status: '/status',
};

function parseLocation(pathname) {
  const runMatch = pathname.match(/^\/runs\/([^/]+)\/?$/);
  if (runMatch) return { page: 'run', runId: decodeURIComponent(runMatch[1]) };
  const clean = pathname.replace(/\/+$/, '') || '/';
  const page = Object.keys(ROUTES).find((k) => ROUTES[k] === clean && k !== 'run');
  return { page: page || 'overview', runId: '' };
}

function pathFor(page, runId) {
  if (page === 'run') return runId ? `/runs/${encodeURIComponent(runId)}` : '/runs';
  return ROUTES[page] || '/';
}

export default function App() {
  const [location, setLocation] = useState(() => parseLocation(window.location.pathname));
  const [lastRunId, setLastRunId] = useState(location.runId);
  const { page, runId } = location;

  const [runs, setRuns] = useState([]);
  const [summary, setSummary] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [resRuns, resAnalytics] = await Promise.all([
        fetch('/api/runs?limit=200').then((r) => (r.ok ? r.json() : null)),
        fetch('/api/analytics/summary').then((r) => (r.ok ? r.json() : null)),
      ]);
      if (resRuns) {
        setRuns(resRuns.runs || []);
        setSummary(resRuns.summary || null);
      }
      if (resAnalytics) setAnalyticsData(resAnalytics);
    } catch (err) {
      console.error('Error fetching data:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Browser Back / Forward.
  useEffect(() => {
    const onPop = () => setLocation(parseLocation(window.location.pathname));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (runId) setLastRunId(runId);
  }, [runId]);

  const navigate = useCallback((nextPage, nextRunId = '') => {
    // "Run details" without an id reopens the last run that was viewed.
    const id = nextPage === 'run' ? nextRunId || lastRunId : '';
    const path = pathFor(nextPage, id);
    if (window.location.pathname !== path) window.history.pushState({}, '', path);
    setLocation({ page: nextPage, runId: id });
    window.scrollTo(0, 0);
  }, [lastRunId]);

  const openRun = (id) => navigate('run', id);

  const handleRunCreated = (newRunId) => {
    fetchData();
    openRun(newRunId);
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans">
      <Sidebar activePage={page} onNavigate={navigate} lastRunId={lastRunId} />

      <main className="flex-1 p-6 md:p-8 overflow-y-auto max-w-7xl">
        {page === 'overview' && (
          <DashboardOverview
            summary={summary}
            recentRuns={runs}
            onNavigate={navigate}
            onSelectRun={openRun}
          />
        )}
        {page === 'generate' && <SingleTaskRun onRunCreated={handleRunCreated} />}
        {page === 'benchmark' && <BatchBenchmark onNavigate={navigate} />}
        {page === 'runs' && <RunsTable runs={runs} onSelectRun={openRun} />}
        {page === 'charts' && <AnalyticsDashboard runs={runs} analyticsData={analyticsData} />}
        {page === 'compare' && <ComparisonsAndStats runs={runs} />}
        {page === 'paper' && <ICoderReference analyticsData={analyticsData} />}
        {page === 'run' && (
          <RunVisualizer runId={runId || lastRunId} onRunIdChange={(id) => navigate('run', id)} />
        )}
        {page === 'status' && <SettingsView />}
      </main>
    </div>
  );
}
