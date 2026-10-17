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

export default function RunsTable({ runs, onSelectRun }) {
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
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <TableProperties className="w-6 h-6 text-indigo-400" />
            <span>Empirical Results & Runs Matrix</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Searchable and filterable benchmark data table covering all evaluated system arms, neutral metrics, and provider tokens.
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
              placeholder="Search Task / Run ID..."
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
              <option value="all">All Modes</option>
              <option value="live">Live API Only</option>
              <option value="simulated">Simulated Only</option>
              <option value="failed">Failed Runs</option>
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
              <option value="all">All Models</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="mini">GPT-4o-mini</option>
              <option value="free">OpenRouter Free</option>
              <option value="fake">Fake</option>
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
              <option value="all">All Categories</option>
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
              <option value="all">All Statuses</option>
              <option value="completed">COMPLETED</option>
              <option value="running">RUNNING</option>
              <option value="failed">FAILED</option>
              <option value="cancelled">CANCELLED</option>
            </select>
          </div>
        </div>

        {/* Sort & Quick Summary Bar */}
        <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 pt-1 font-mono border-t border-slate-800/60 mt-2">
          <div className="flex items-center gap-3">
            <span>
              Showing <span className="text-white font-bold">{filteredRuns.length}</span> runs
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-cyan-400">Mean Quality: {viewStats.avgQuality.toFixed(3)}</span>
            <span className="text-slate-600">|</span>
            <span className="text-amber-400">Mean Tokens: {viewStats.avgTokens.toLocaleString()}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-500">Sort:</span>
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
              Q/1K {sortBy === 'quality_per_1k' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
            <button
              onClick={() => toggleSort('duration')}
              className={`hover:text-slate-200 ${sortBy === 'duration' ? 'text-slate-200 font-bold' : ''}`}
            >
              Duration {sortBy === 'duration' ? (sortOrder === 'desc' ? '↓' : '↑') : ''}
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] border-b border-slate-800">
            <tr>
              <th className="py-3 px-3">Run ID / Task</th>
              <th className="py-3 px-2 text-center">Mode</th>
              <th className="py-3 px-2">Cat.</th>
              <th className="py-3 px-2">Sys</th>
              <th className="py-3 px-2">Model</th>
              <th className="py-3 px-2 text-center">Status</th>
              <th className="py-3 px-3 text-right">Quality</th>
              <th className="py-3 px-2 text-right">Comp</th>
              <th className="py-3 px-2 text-right">Exec</th>
              <th className="py-3 px-2 text-right">Cons</th>
              <th className="py-3 px-2 text-right">Test</th>
              <th className="py-3 px-2 text-right">Ruff</th>
              <th className="py-3 px-2 text-right">Bandit</th>
              <th className="py-3 px-2 text-right">Radon</th>
              <th className="py-3 px-3 text-right">Tokens</th>
              <th className="py-3 px-2 text-right">Cost</th>
              <th className="py-3 px-2 text-right">Dur</th>
              <th className="py-3 px-2 text-center">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {paginatedRuns.length > 0 ? (
              paginatedRuns.map((r) => (
                <tr key={r.run_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2.5 px-3">
                    <div className="font-semibold text-slate-200 truncate max-w-[140px]">{r.run_id}</div>
                    <div className="text-[10px] text-slate-500 truncate max-w-[140px]">{r.task_id}</div>
                  </td>
                  <td className="py-2.5 px-2 text-center">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                        r.execution_mode === 'SKIPPED' || r.status === 'SKIPPED' || r.status === 'NOT_STARTED'
                          ? 'bg-slate-800 text-slate-300 border border-slate-700'
                          : (r.execution_mode === 'LIVE_API' || (r.model !== 'fake' && r.execution_mode !== 'SIMULATED'))
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60'
                          : 'bg-amber-950 text-amber-300 border border-amber-800/60'
                      }`}
                      title={
                        r.execution_mode === 'SKIPPED' || r.status === 'SKIPPED'
                          ? (r.skip_reason || r.failure_reason || 'Skipped Execution (Not Invoked)')
                          : r.execution_mode === 'LIVE_API'
                          ? 'Live API Execution'
                          : 'Simulated / Fake Execution'
                      }
                    >
                      {r.execution_mode === 'SKIPPED' || r.status === 'SKIPPED' ? 'SKIP' : r.execution_mode === 'LIVE_API' ? 'LIVE' : 'SIM'}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 text-slate-400 text-[11px]">{r.category || 'Creation'}</td>
                  <td className="py-2.5 px-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                        r.system === 'chatdev' ? 'bg-amber-950 text-amber-400' : 'bg-indigo-950 text-indigo-400'
                      }`}
                    >
                      {r.system}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 text-slate-300 text-[11px] truncate max-w-[90px]">{r.model}</td>
                  <td className="py-2.5 px-2 text-center">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                        r.status === 'COMPLETED'
                          ? 'bg-emerald-950 text-emerald-400'
                          : r.status === 'RUNNING'
                          ? 'bg-cyan-950 text-cyan-300 animate-pulse'
                          : r.status === 'SKIPPED' || r.status === 'NOT_STARTED'
                          ? 'bg-slate-800 text-slate-300 border border-slate-700'
                          : r.status === 'MODEL_MISMATCH_DIAGNOSTIC' || r.status === 'DIAGNOSTIC_RUN'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800/40'
                          : 'bg-rose-950 text-rose-400'
                      }`}
                      title={r.status === 'SKIPPED' ? (r.skip_reason || 'Skipped Execution') : (r.failure_reason || r.status)}
                    >
                      {r.status || 'OK'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-cyan-300">{r.quality?.toFixed(3) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-300">{r.completeness?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-300">{r.executability?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-300">{r.consistency?.toFixed(3) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-emerald-400">{r.shared_test?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-400">{r.ruff?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-400">{r.bandit?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-2 text-right text-slate-400">{r.radon?.toFixed(2) ?? '-'}</td>
                  <td className="py-2.5 px-3 text-right text-amber-300 font-semibold">
                    {r.tokens != null && r.tokens > 0 ? r.tokens.toLocaleString() : (r.token_provenance === 'UNAVAILABLE' ? 'N/A' : '0')}
                  </td>
                  <td className="py-2.5 px-2 text-right text-violet-300">${(r.estimated_cost ?? 0).toFixed(4)}</td>
                  <td className="py-2.5 px-2 text-right text-slate-400">
                    {r.duration_seconds ? `${r.duration_seconds}s` : '-'}
                  </td>
                  <td className="py-2.5 px-2 text-center">
                    <button
                      onClick={() => onSelectRun(r.run_id)}
                      className="p-1 hover:bg-cyan-900/60 text-cyan-400 rounded transition-colors"
                      title="Inspect Run"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={18} className="py-8 text-center text-slate-500 italic">
                  No runs matching the selected filters.
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
            Page <span className="text-white font-bold">{currentPage}</span> of {totalPages}
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
