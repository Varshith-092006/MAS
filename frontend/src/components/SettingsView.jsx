import React, { useState } from 'react';
import {
  Settings,
  ShieldCheck,
  Database,
  Cpu,
  Terminal,
  Key,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
} from 'lucide-react';

export default function SettingsView() {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const runDiagnostics = async () => {
    setTesting(true);
    const start = performance.now();
    try {
      const [resHealth, resRuns, resAnalytics] = await Promise.all([
        fetch('/health').then((r) => r.json()).catch(() => null),
        fetch('/api/runs?limit=1').then((r) => r.json()).catch(() => null),
        fetch('/api/analytics/summary').then((r) => r.json()).catch(() => null),
      ]);
      const latency = Math.round(performance.now() - start);

      setTestResult({
        success: !!resHealth && !!resRuns,
        latency,
        health: resHealth,
        runsCount: resRuns?.total_count || resRuns?.runs?.length || 0,
        analyticsOk: !!resAnalytics,
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      setTestResult({
        success: false,
        error: err.message,
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Settings className="w-6 h-6 text-slate-400" />
            <span>Research System Configuration & Environment</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Active runtime boundaries, database configuration, model providers, and safety envelopes.
          </p>
        </div>

        <button
          onClick={runDiagnostics}
          disabled={testing}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 text-white rounded-lg text-xs font-bold transition-colors flex items-center gap-2 shadow-sm font-mono"
        >
          {testing ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Pinging Services...</span>
            </>
          ) : (
            <>
              <Activity className="w-3.5 h-3.5" />
              <span>Run System Diagnostics</span>
            </>
          )}
        </button>
      </div>

      {/* Diagnostics Result Card */}
      {testResult && (
        <div
          className={`p-4 rounded-xl border text-xs font-mono flex items-start justify-between gap-3 ${
            testResult.success
              ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/60 border-rose-800 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-3">
            {testResult.success ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            )}
            <div className="space-y-0.5">
              <div className="font-bold">
                {testResult.success ? 'All Services Healthy & Online' : 'Service Connection Warning'}
              </div>
              <div className="text-[11px] opacity-80">
                API Ping: {testResult.latency}ms • Database Records: {testResult.runsCount} runs • Analytics Engine: {testResult.analyticsOk ? 'Operational' : 'Degraded'}
              </div>
            </div>
          </div>
          <span className="text-[10px] text-slate-400 whitespace-nowrap">{testResult.timestamp}</span>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6 font-mono text-xs">
        {/* Runtime Environment */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-200">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span>Python & Host Environment</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-slate-400">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Python Runtime:</span>
              <span className="text-white font-bold">Python 3.11</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Temperature:</span>
              <span className="text-white font-bold">0.0 (Deterministic)</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Evaluation Seed:</span>
              <span className="text-white font-bold">42</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Benchmark Suite:</span>
              <span className="text-white font-bold">SRDD-20 Standard</span>
            </div>
          </div>
        </div>

        {/* AI Provider */}
        <div className="space-y-3 pt-3 border-t border-slate-800">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-200">
            <Key className="w-4 h-4 text-amber-400" />
            <span>AI Provider & Routing</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-slate-400">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Provider:</span>
              <span className="text-emerald-400 font-bold">OpenRouter / OpenAI Compatible</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Endpoint URL:</span>
              <span className="text-slate-200">https://openrouter.ai/api/v1</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Token Tracking:</span>
              <span className="text-emerald-400 font-bold">Local Logging Proxy (Port 8089)</span>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Audit Table:</span>
              <span className="text-slate-200">SQLite / PostgreSQL (Append-Only)</span>
            </div>
          </div>
        </div>

        {/* Safety Budget Caps */}
        <div className="space-y-3 pt-3 border-t border-slate-800">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-200">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>Safety Budget Caps & Token Envelopes</span>
          </div>
          <div className="p-3 bg-slate-950 rounded-lg border border-indigo-900/40 text-slate-300 space-y-1">
            <div>• <strong>GPT-4o Main Arm Cap:</strong> 40,000 tokens / run maximum</div>
            <div>• <strong>GPT-4o-mini Arm Cap:</strong> 20,000 tokens / run maximum</div>
            <div>• <strong>Max Iterations:</strong> 3 iterations with adaptive early exit</div>
            <div>• <strong>Sandboxing:</strong> Isolated container execution with timeout safeguards</div>
          </div>
        </div>
      </div>
    </div>
  );
}
