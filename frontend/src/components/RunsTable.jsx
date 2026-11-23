import React, { useState, useMemo } from 'react';
import {
  TableProperties,
  Search,
  Filter,
  ArrowUpDown,
  ExternalLink,
  Download,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  Cpu,
  Clock,
  Award,
} from 'lucide-react';

const SYSTEM_NAMES = { mas: 'MAS', chatdev: 'ChatDev', single: 'Single agent' };
const STATUS_NAMES = {
  COMPLETED: 'Finished',
  RUNNING: 'Running',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  SKIPPED: 'Skipped',
  NOT_STARTED: 'Not started',
  MODEL_MISMATCH_DIAGNOSTIC: 'Diagnostic',
  DIAGNOSTIC_RUN: 'Diagnostic',
};

export default function RunsTable({ runs, onSelectRun }) {
  const modelOptions = useMemo(
    () => [...new Set((runs || []).map((r) => r.model).filter(Boolean))].sort(),
    [runs]
  );
  const [searchTerm, setSearchTerm] = useState('');
  const [modeFilter, setModeFilter] = useState('all');
  const [systemFilter, setSystemFilter] = useState('all');
  const [modelFilter, setModelFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('quality');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const filteredRuns = useMemo(() => {
    if (!runs) return [];

    return runs
      .filter((r) => {
        if (searchTerm) {
          const s = searchTerm.toLowerCase();
          const matchId = r.run_id?.toLowerCase().includes(s);
          const matchTask = r.task_id?.toLowerCase().includes(s);
          if (!matchId && !matchTask) return false;
        }
        if (modeFilter !== 'all') {
          const rMode = (r.execution_mode || (r.model === 'fake' ? 'SIMULATED' : 'LIVE_API')).toUpperCase();
          if (modeFilter === 'live' && rMode !== 'LIVE_API') return false;
          if (modeFilter === 'simulated' && rMode !== 'SIMULATED') return false;
          if (modeFilter === 'failed' && r.status?.toUpperCase() !== 'FAILED') return false;
        }
        if (systemFilter !== 'all' && r.system?.toLowerCase() !== systemFilter.toLowerCase()) {
          return false;
        }
        if (modelFilter !== 'all' && !r.model?.toLowerCase().includes(modelFilter.toLowerCase())) {
          return false;
        }
        if (categoryFilter !== 'all' && r.category?.toLowerCase() !== categoryFilter.toLowerCase()) {
          return false;
        }
        if (statusFilter !== 'all' && r.status?.toUpperCase() !== statusFilter.toUpperCase()) {
          return false;
        }
        return true;
      })
      .sort((a, b) => {
        let valA = 0;
        let valB = 0;

        if (sortBy === 'quality') {
          valA = a.quality ?? 0;
          valB = b.quality ?? 0;
        } else if (sortBy === 'tokens') {
          valA = a.tokens ?? 0;
          valB = b.tokens ?? 0;
        } else if (sortBy === 'quality_per_1k') {
          valA = a.quality_per_1k ?? 0;
          valB = b.quality_per_1k ?? 0;
        } else if (sortBy === 'duration') {
          valA = a.duration_seconds ?? 0;
          valB = b.duration_seconds ?? 0;
        }

        return sortOrder === 'desc' ? valB - valA : valA - valB;
      });
  }, [runs, searchTerm, modeFilter, systemFilter, modelFilter, categoryFilter, statusFilter, sortBy, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredRuns.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedRuns = filteredRuns.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Filtered view summary statistics
  const viewStats = useMemo(() => {
    if (!filteredRuns.length) return { avgQuality: 0, avgTokens: 0, totalCost: 0, avgDuration: 0 };
    const n = filteredRuns.length;
    const sumQ = filteredRuns.reduce((acc, r) => acc + (r.quality || 0), 0);
    const sumTok = filteredRuns.reduce((acc, r) => acc + (r.tokens || 0), 0);
    const sumCost = filteredRuns.reduce((acc, r) => acc + (r.estimated_cost || 0), 0);
    const sumDur = filteredRuns.reduce((acc, r) => acc + (r.duration_seconds || 0), 0);
    return {
      avgQuality: sumQ / n,
      avgTokens: Math.round(sumTok / n),
      totalCost: sumCost,
      avgDuration: (sumDur / n).toFixed(1),
    };
  }, [filteredRuns]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const exportCSV = () => {
    if (!filteredRuns.length) return;
    const headers = [
      'run_id', 'task_id', 'category', 'system', 'model', 'actual_model', 'experimental_condition', 'eligibility_status', 'repeat_no', 'status',
      'execution_mode', 'token_provenance', 'failure_reason', 'skip_reason',
      'quality', 'completeness', 'executability', 'consistency', 'shared_test',
      'ruff', 'bandit', 'radon', 'tokens', 'cost', 'duration'
    ];
    const rows = filteredRuns.map((r) => [
      r.run_id, r.task_id, r.category, r.system, r.model, r.actual_model || r.model,
      r.benchmark || (r.model?.includes(':free') ? 'FREE_MODEL_EXPLORATORY' : 'GPT4O_RESEARCH'),
      r.eligibility_status || (r.status === 'COMPLETED' ? 'ELIGIBLE' : 'EXCLUDED'),
      r.repeat_no, r.status,
      r.execution_mode || '', r.token_provenance || 'UNAVAILABLE',
      `"${(r.failure_reason || '').replace(/"/g, '""')}"`, `"${(r.skip_reason || '').replace(/"/g, '""')}"`,
      r.quality ?? 'N/A', r.completeness ?? 'N/A', r.executability ?? 'N/A', r.consistency ?? 'N/A', r.shared_test ?? 'N/A',
      r.ruff ?? 'N/A', r.bandit ?? 'N/A', r.radon ?? 'N/A', r.tokens ?? 'N/A', r.estimated_cost ?? 0, r.duration_seconds ?? 'N/A'
    ]);

    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'mas_research_runs.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2">
            <TableProperties className="w-6 h-6 text-indigo-400" />
            <span>All Runs</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Every run saved in the database. Click a row to see its code, agent steps and scores.
          </p>
        </div>

        <button
          onClick={exportCSV}
          className="flex items-center gap-2 px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors shadow-sm"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export CSV</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
          {/* Search */}
          <div className="relative md:col-span-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by run or task…"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>

          {/* Execution Mode */}
          <div>
            <select
              value={modeFilter}
              onChange={(e) => {
                setModeFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none"
            >
              <option value="all">Live and test runs</option>
              <option value="live">Live model only</option>
              <option value="simulated">Offline test only</option>
              <option value="failed">Failed only</option>
            </select>
          </div>

          {/* System */}
          <div>
            <select
              value={systemFilter}
              onChange={(e) => {
                setSystemFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none"
            >
              <option value="all">All Systems</option>
              <option value="mas">MAS</option>
              <option value="chatdev">ChatDev</option>
              <option value="single">Single agent</option>
            </select>
          </div>

          {/* Model */}
          <div>
            <select
              value={modelFilter}
              onChange={(e) => {
                setModelFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none"
            >
              <option value="all">All models</option>
              {modelOptions.map((m) => (
                <option key={m} value={m}>{m === 'fake' ? 'Offline test' : m}</option>
              ))}
            </select>
          </div>

          {/* Category */}
          <div>
            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none"
            >
              <option value="all">All categories</option>
              <option value="creation">Creation</option>
              <option value="education">Education</option>
              <option value="work">Work</option>
              <option value="life">Life</option>
              <option value="games">Games</option>
            </select>
          </div>

          {/* Status */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono focus:outline-none"
            >
              <option value="all">All statuses</option>
              <option value="completed">Finished</option>
              <option value="running">Running</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        {/* Sort & Quick Summary Bar */}
        <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 pt-1 font-mono border-t border-slate-800/60 mt-2">
          <div className="flex items-center gap-3">
            <span>
              Showing <span className="text-slate-50 font-bold">{filteredRuns.length}</span> runs
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-cyan-400">Average quality: {viewStats.avgQuality.toFixed(3)}</span>
            <span className="text-slate-600">|</span>
            <span className="text-amber-400">Average tokens: {Math.round(viewStats.avgTokens).toLocaleString()}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-500">Sort by:</span>
            <button
              onClick={() => toggleSort('quality')}
              className={`hover:text-cyan-400 ${sortBy === 'quality' ? 'text-cyan-400 font-bold' : ''}`}
            >
              Quality {sortBy === 'quality' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
            <button
              onClick={() => toggleSort('tokens')}
              className={`hover:text-amber-400 ${sortBy === 'tokens' ? 'text-amber-400 font-bold' : ''}`}
            >
              Tokens {sortBy === 'tokens' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
            <button
              onClick={() => toggleSort('quality_per_1k')}
              className={`hover:text-teal-400 ${sortBy === 'quality_per_1k' ? 'text-teal-400 font-bold' : ''}`}
            >
              Quality per 1K tokens {sortBy === 'quality_per_1k' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
            <button
              onClick={() => toggleSort('duration')}
              className={`hover:text-slate-200 ${sortBy === 'duration' ? 'text-slate-200 font-bold' : ''}`}
            >
              Time {sortBy === 'duration' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-800 rounded-lg overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-925 text-slate-500 text-[11px] border-b border-slate-800">
            <tr>
              <th className="py-3 px-3 font-semibold">Run / task</th>
              <th className="py-3 px-2 font-semibold">System</th>
              <th className="py-3 px-2 font-semibold">Category</th>
              <th className="py-3 px-2 font-semibold">Type</th>
              <th className="py-3 px-2 font-semibold">Status</th>
              <th className="py-3 px-3 text-right font-semibold" title="Complete × Runs × Matches requirement">Quality</th>
              <th className="py-3 px-2 text-right font-semibold" title="Share of functions that are fully implemented">Complete</th>
              <th className="py-3 px-2 text-right font-semibold" title="Yes = the program runs without error">Runs</th>
              <th className="py-3 px-2 text-right font-semibold" title="How closely the code matches the requirement text (0 to 1)">Matches req.</th>
              <th className="py-3 px-3 text-right font-semibold">Tokens</th>
              <th className="py-3 px-2 text-right font-semibold">Time</th>
              <th className="py-3 px-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {paginatedRuns.length > 0 ? (
              paginatedRuns.map((r) => {
                const skipped = r.execution_mode === 'SKIPPED' || r.status === 'SKIPPED' || r.status === 'NOT_STARTED';
                const live = r.execution_mode === 'LIVE_API' || (r.model !== 'fake' && r.execution_mode !== 'SIMULATED');
                return (
                  <tr key={r.run_id} className="hover:bg-slate-925 cursor-pointer" onClick={() => onSelectRun(r.run_id)}>
                    <td className="py-2.5 px-3">
                      <div className="font-medium text-slate-200 truncate max-w-[180px]">{r.run_id}</div>
                      <div className="text-[11px] text-slate-500 truncate max-w-[180px]">{r.task_id}</div>
                    </td>
                    <td className="py-2.5 px-2 text-slate-300">{SYSTEM_NAMES[r.system] || r.system}</td>
                    <td className="py-2.5 px-2 text-slate-400">{r.category || '-'}</td>
                    <td className="py-2.5 px-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[11px] ${
                          skipped ? 'bg-slate-850 text-slate-400' : live ? 'bg-cyan-950 text-cyan-400' : 'bg-amber-950 text-amber-400'
                        }`}
                        title={r.model}
                      >
                        {skipped ? 'Skipped' : live ? 'Live' : 'Test'}
                      </span>
                    </td>
                    <td className="py-2.5 px-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[11px] ${
                          r.status === 'COMPLETED'
                            ? 'bg-emerald-950 text-emerald-400'
                            : r.status === 'RUNNING'
                            ? 'bg-cyan-950 text-cyan-400'
                            : skipped
                            ? 'bg-slate-850 text-slate-400'
                            : STATUS_NAMES[r.status] === 'Diagnostic'
                            ? 'bg-amber-950 text-amber-400'
                            : 'bg-rose-950 text-rose-400'
                        }`}
                        title={r.failure_reason || r.skip_reason || r.status}
                      >
                        {STATUS_NAMES[r.status] || r.status || '-'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right font-semibold text-slate-100">{r.quality != null ? r.quality.toFixed(3) : '-'}</td>
                    <td className="py-2.5 px-2 text-right text-slate-300">{r.completeness != null ? r.completeness.toFixed(2) : '-'}</td>
                    <td className="py-2.5 px-2 text-right text-slate-300">
                      {r.executability != null ? (r.executability >= 1 ? 'Yes' : 'No') : '-'}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-300">{r.consistency != null ? r.consistency.toFixed(3) : '-'}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">
                      {r.tokens != null && r.tokens > 0 ? r.tokens.toLocaleString() : r.token_provenance === 'UNAVAILABLE' ? 'N/A' : '0'}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-400">
                      {r.duration_seconds ? `${Math.round(r.duration_seconds)}s` : '-'}
                    </td>
                    <td className="py-2.5 px-2 text-center">
                      <ExternalLink className="w-3.5 h-3.5 text-cyan-500 inline" />
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={12} className="py-8 text-center text-slate-500">
                  No runs match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
          <div>
            Page <span className="text-slate-50 font-bold">{currentPage}</span> of {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
