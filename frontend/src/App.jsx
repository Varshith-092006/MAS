import React, { useState, useEffect } from 'react';
import RunHeader from './components/RunHeader';
import StatusBanner from './components/StatusBanner';
import AgentLog from './components/AgentLog';
import MetricsTable from './components/MetricsTable';
import TokenCostChart from './components/TokenCostChart';

export default function App() {
  const [runId, setRunId] = useState(() => {
    // Extract runId from path /runs/:runId if present
    const path = window.location.pathname;
    const match = path.match(/\/runs\/([^/]+)/);
    return match ? match[1] : '';
  });

  const [inputRunId, setInputRunId] = useState(runId);
  const [runData, setRunData] = useState(null);
  const [metrics, setMetrics] = useState({ neutral: {}, internal: {} });
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRunData = async (targetId) => {
    if (!targetId) return;
    setLoading(true);
    setError(null);
    try {
      const [resRun, resMetrics, resEvents] = await Promise.all([
        fetch(`/api/runs/${targetId}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/runs/${targetId}/results`).then((r) => (r.ok ? r.json() : null)),
        fetch(`/api/runs/${targetId}/events`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (!resRun) {
        setError(`Run ID '${targetId}' not found.`);
      } else {
        setRunData(resRun);
        if (resMetrics) setMetrics(resMetrics);
        if (resEvents) setEvents(resEvents);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (runId) {
      fetchRunData(runId);

      // Connect WebSocket for live event streaming
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/runs/${runId}`;
      let ws;
      try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data);
            if (data.event) {
              setEvents((prev) => [...prev, data]);
              // Refresh metrics and run details
              fetchRunData(runId);
            }
          } catch (e) {}
        };
      } catch (e) {}

      return () => {
        if (ws) ws.close();
      };
    }
  }, [runId]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputRunId.trim()) {
      setRunId(inputRunId.trim());
      window.history.pushState({}, '', `/runs/${inputRunId.trim()}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Run Selector Bar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl mb-6 shadow-md flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-300">MAS Run Visualizer (/runs/:runId)</div>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            placeholder="Enter Run ID..."
            value={inputRunId}
            onChange={(e) => setInputRunId(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-100 text-xs px-3 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 font-mono w-64"
          />
          <button
            type="submit"
            className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold px-4 py-1.5 rounded-lg transition-colors"
          >
            Load Run
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-rose-950/70 border border-rose-800 text-rose-300 p-4 rounded-xl mb-6 text-sm">
          {error}
        </div>
      )}

      {runData && (
        <>
          <RunHeader runData={runData} />
          <StatusBanner
            status={runData.status}
            complexity={runData.complexity}
            iteration={runData.iteration}
            stopReason={runData.stop_reason}
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <AgentLog events={events} />
            <TokenCostChart
              tokens={runData.total_tokens}
              cost={runData.estimated_cost}
              quality={metrics?.neutral?.quality}
            />
          </div>

          <MetricsTable metrics={metrics} tokens={runData.total_tokens} />
        </>
      )}

      {!runData && !error && (
        <div className="text-center py-20 text-slate-500">
          <p className="text-base font-medium">Enter a Run ID above or visit <span className="font-mono text-cyan-400">/runs/:runId</span> to monitor execution.</p>
        </div>
      )}
    </div>
  );
}
