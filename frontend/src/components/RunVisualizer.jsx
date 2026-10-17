import React, { useState, useEffect } from 'react';
import {
  MonitorDot,
  Loader2,
  AlertCircle,
  Clock,
  Cpu,
  Layers,
  Award,
  DollarSign,
  Zap,
  CheckCircle2,
  RefreshCw,
  Code2,
  Boxes,
  GitPullRequest,
  StopCircle,
  PlayCircle,
  BarChart2,
} from 'lucide-react';
import RunHeader from './RunHeader';
import StatusBanner from './StatusBanner';
import AgentLog from './AgentLog';
import MetricsTable from './MetricsTable';
import TokenCostChart from './TokenCostChart';
import WorkspaceExplorer from './WorkspaceExplorer';
import ArtifactsInspector from './ArtifactsInspector';
import ChangeRequestModal from './ChangeRequestModal';

export default function RunVisualizer({ runId: initialRunId, onRunIdChange, onCloneRun }) {
  const [currentId, setCurrentId] = useState(initialRunId || '');
  const [inputRunId, setInputRunId] = useState(initialRunId || '');
  const [runData, setRunData] = useState(null);
  const [metrics, setMetrics] = useState({ neutral: {}, internal: {} });
  const [events, setEvents] = useState([]);
  const [activeSubTab, setActiveSubTab] = useState('telemetry'); // 'telemetry', 'workspace', 'artifacts'
  const [showChangeModal, setShowChangeModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (initialRunId) {
      setCurrentId(initialRunId);
      setInputRunId(initialRunId);
    }
  }, [initialRunId]);

  const fetchRunDetails = async (targetId) => {
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
    if (currentId) {
      fetchRunDetails(currentId);

      // WebSocket live event streaming
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/runs/${currentId}`;
      let ws;
      try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data);
            if (data.event) {
              setEvents((prev) => [...prev, data]);
              fetchRunDetails(currentId);
            }
          } catch (e) {}
        };
      } catch (e) {}

      return () => {
        if (ws) ws.close();
      };
    }
  }, [currentId]);

  const handleLoad = (e) => {
    e.preventDefault();
    if (inputRunId.trim()) {
      const cleaned = inputRunId.trim();
      setCurrentId(cleaned);
      if (onRunIdChange) onRunIdChange(cleaned);
    }
  };

  const handleCancelRun = async () => {
    if (!currentId) return;
    if (!window.confirm(`Are you sure you want to cancel Run ${currentId}?`)) return;
    setCancelling(true);
    try {
      const res = await fetch(`/api/runs/${currentId}/cancel`, { method: 'POST' });
      if (res.ok) {
        fetchRunDetails(currentId);
      }
    } catch (err) {
      console.error('Cancel error:', err);
    } finally {
      setCancelling(false);
    }
  };

  // Agent timeline list
  const pipelineAgents = [
    'manager',
    'router',
    'architect',
    'developer',
    'ast',
    'shared_test',
    'ruff',
    'bandit',
    'radon',
    'reviewer',
    'reflection',
  ];

  // Determine active/completed agents from events
  const agentStatuses = pipelineAgents.map((ag) => {
    const hasSuccess = events.some(
      (e) => e.agent?.toLowerCase() === ag && (e.status === 'success' || e.event?.includes('completed'))
    );
    const hasStarted = events.some((e) => e.agent?.toLowerCase() === ag);
    return {
      agent: ag,
      status: hasSuccess ? 'completed' : hasStarted ? 'active' : 'pending',
    };
  });

  const neutral = metrics?.neutral || {};
  const internal = metrics?.internal || {};
  const hasValidTokens = runData?.total_tokens != null && runData.total_tokens > 0;
  const quality = neutral.quality ?? internal.adaptive_score ?? 0;
  const qPer1k = hasValidTokens && quality > 0 ? (quality / (runData.total_tokens / 1000)).toFixed(4) : 'N/A';

  return (
    <div className="space-y-6">
      {/* Search / Run ID Bar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <MonitorDot className="w-5 h-5 text-cyan-400" />
          <span className="text-sm font-bold text-white">MAS Run Visualizer</span>
          <span className="text-xs font-mono text-slate-400">(/runs/:runId)</span>
        </div>

        <form onSubmit={handleLoad} className="flex gap-2">
          <input
            type="text"
            placeholder="Enter Run ID..."
            value={inputRunId}
            onChange={(e) => setInputRunId(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-100 text-xs px-3 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 font-mono w-64"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold px-4 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
            <span>Load Run</span>
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-rose-950/70 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {runData ? (
        <>
          {/* Header & Status Banner */}
          <RunHeader runData={runData} />

          {/* Action Ribbon & Sub-Tab Navigation */}
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-xl shadow-md flex flex-wrap items-center justify-between gap-3">
            {/* View Selection Tabs */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button
                onClick={() => setActiveSubTab('telemetry')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                  activeSubTab === 'telemetry'
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BarChart2 className="w-3.5 h-3.5" />
                <span>Telemetry & Metrics</span>
              </button>

              <button
                onClick={() => setActiveSubTab('workspace')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                  activeSubTab === 'workspace'
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>Generated Code</span>
              </button>

              <button
                onClick={() => setActiveSubTab('artifacts')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                  activeSubTab === 'artifacts'
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Boxes className="w-3.5 h-3.5" />
                <span>Agent Artifacts</span>
              </button>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowChangeModal(true)}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
                title="Apply requirement evolution"
              >
                <GitPullRequest className="w-3.5 h-3.5" />
                <span>Change Request</span>
              </button>

              {runData.status === 'RUNNING' && (
                <button
                  onClick={handleCancelRun}
                  disabled={cancelling}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  title="Cancel active execution"
                >
                  <StopCircle className="w-3.5 h-3.5" />
                  <span>{cancelling ? 'Cancelling...' : 'Cancel Run'}</span>
                </button>
              )}

              <button
                onClick={() => fetchRunDetails(currentId)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                title="Refresh Run"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
              </button>
            </div>
          </div>

          <StatusBanner
            status={runData.status}
            complexity={runData.complexity}
            iteration={runData.iteration}
            stopReason={runData.stop_reason}
          />

          {/* Sub-Tab 1: Telemetry & Metrics */}
          {activeSubTab === 'telemetry' && (
            <div className="space-y-6">
              {/* Agent Lifecycle Pipeline Timeline */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Agent Lifecycle Pipeline Timeline
                  </span>
                  <span className="text-[11px] font-mono text-cyan-400">Live State Tracking</span>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {agentStatuses.map((item, idx) => {
                    let badgeClass = 'bg-slate-950 text-slate-500 border-slate-800';
                    if (item.status === 'completed') {
                      badgeClass = 'bg-emerald-950 text-emerald-400 border-emerald-800';
                    } else if (item.status === 'active') {
                      badgeClass = 'bg-cyan-950 text-cyan-300 border-cyan-800 animate-pulse';
                    }

                    return (
                      <div key={idx} className="flex items-center gap-1.5">
                        <div className={`px-2.5 py-1 rounded-md text-[11px] font-mono uppercase border ${badgeClass}`}>
                          {item.agent}
                        </div>
                        {idx < agentStatuses.length - 1 && (
                          <span className="text-slate-600 text-xs">→</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Token Consumption & Telemetry */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
                  Token Consumption & Telemetry
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-[10px]">Input Tokens</div>
                    <div className="text-base font-bold text-slate-200 mt-0.5">
                      {(runData.input_tokens || 0).toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-[10px]">Output Tokens</div>
                    <div className="text-base font-bold text-slate-200 mt-0.5">
                      {(runData.output_tokens || 0).toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-[10px]">Total Tokens</div>
                    <div className="text-base font-bold text-amber-300 mt-0.5">
                      {(runData.total_tokens || 0).toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-[10px]">Estimated Cost</div>
                    <div className="text-base font-bold text-violet-300 mt-0.5">
                      ${(runData.estimated_cost || 0).toFixed(4)}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-[10px]">Quality / 1K Tokens</div>
                    <div className="text-base font-bold text-teal-300 mt-0.5">{qPer1k}</div>
                  </div>
                </div>
              </div>

              {/* Agent Audit Log and Cost Chart */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <AgentLog events={events} />
                <TokenCostChart
                  tokens={runData.total_tokens}
                  cost={runData.estimated_cost}
                  quality={quality}
                />
              </div>

              {/* Full Metrics Table */}
              <MetricsTable metrics={metrics} tokens={runData.total_tokens} />
            </div>
          )}

          {/* Sub-Tab 2: Generated Code & Workspace */}
          {activeSubTab === 'workspace' && (
            <WorkspaceExplorer runId={currentId} />
          )}

          {/* Sub-Tab 3: Inter-Agent Artifacts */}
          {activeSubTab === 'artifacts' && (
            <ArtifactsInspector runId={currentId} />
          )}

          {/* Requirement Change Request Modal */}
          {showChangeModal && (
            <ChangeRequestModal
              runId={currentId}
              originalRequirement={runData.task_id}
              onClose={() => setShowChangeModal(false)}
              onSuccess={() => {
                fetchRunDetails(currentId);
              }}
            />
          )}
        </>
      ) : (
        !error && (
          <div className="text-center py-20 text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
            <p className="text-sm font-medium">
              Enter a Run ID above or select a run from the Runs table to inspect live metrics, generated code, and events.
            </p>
          </div>
        )
      )}
    </div>
  );
}
