import React, { useState } from 'react';
import {
  Layers,
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Play,
  ShieldAlert,
  Loader2,
  FileJson,
  Sparkles,
} from 'lucide-react';

export default function BatchBenchmark({ onNavigate }) {
  const [inputTab, setInputTab] = useState('paste'); // 'paste', 'json', 'csv'
  const [taskText, setTaskText] = useState(
    JSON.stringify(
      [
        {
          task_id: 'task_001',
          requirement: 'Build a calculator application with add, subtract, multiply, and divide functions.',
          category: 'Creation',
        },
        {
          task_id: 'task_002',
          requirement: 'Build a personal expense tracker with budget categories and monthly summaries.',
          category: 'Life',
        },
        {
          task_id: 'task_003',
          requirement: 'Build a flashcard study tool with spaced repetition intervals.',
          category: 'Education',
        },
      ],
      null,
      2
    )
  );

  const [taskCount, setTaskCount] = useState(3);
  const [repeats, setRepeats] = useState(1);
  const [systems, setSystems] = useState({ mas: true, chatdev: true });
  const [models, setModels] = useState({ 'openrouter/free': true, 'fake': false, 'gpt-4o': false, 'gpt-4o-mini': false });
  const [seed, setSeed] = useState(42);
  const [temperature, setTemperature] = useState(0.0);

  const [validationResult, setValidationResult] = useState(null);
  const [dryRunData, setDryRunData] = useState(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [benchmarkStarted, setBenchmarkStarted] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Parse tasks from input
  const getParsedTasks = () => {
    try {
      if (inputTab === 'csv') {
        const lines = taskText.trim().split('\n');
        if (lines.length <= 1) return [];
        return lines.slice(1).map((line, idx) => {
          const parts = line.split(',');
          return {
            task_id: parts[0]?.trim() || `task_${String(idx + 1).padStart(3, '0')}`,
            requirement: parts[1]?.trim() || 'Software requirement',
            category: parts[2]?.trim() || 'Creation',
          };
        });
      }
      const parsed = JSON.parse(taskText);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return null;
    }
  };

  const selectedSystems = Object.keys(systems).filter((k) => systems[k]);
  const selectedModels = Object.keys(models).filter((k) => models[k]);
  const currentTaskCount = Number(taskCount) || 3;
  const currentRepeats = Number(repeats) || 1;
  const plannedRuns = currentTaskCount * currentRepeats * selectedSystems.length * selectedModels.length;

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target.result;
      setTaskText(content);
      try {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed)) {
          setTaskCount(parsed.length);
        }
      } catch (err) {}
    };
    reader.readAsText(file);
  };

  const handleValidate = () => {
    setError(null);
    const tasks = getParsedTasks();
    if (!tasks) {
      setError('Invalid task format. Please provide valid JSON array of tasks or CSV.');
      return;
    }
    if (tasks.length === 0) {
      setError('No tasks found in input.');
      return;
    }
    setTaskCount(tasks.length);
    setValidationResult({
      status: 'VALID',
      tasks_count: tasks.length,
      systems_count: selectedSystems.length,
      models_count: selectedModels.length,
      repeats: currentRepeats,
      planned_runs: tasks.length * currentRepeats * selectedSystems.length * selectedModels.length,
    });
  };

  const handleDryRun = async () => {
    setError(null);
    setLoading(true);
    try {
      const tasks = getParsedTasks();
      const res = await fetch('/api/evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tasks: tasks && tasks.length > 0 ? tasks : null,
          task_count: currentTaskCount,
          systems: selectedSystems,
          models: selectedModels,
          repeats: currentRepeats,
          seed: Number(seed),
          temperature: Number(temperature),
          dry_run: true,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Failed to run dry-run validation (${res.status})`);
      }

      const data = await res.json();
      setDryRunData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmStart = async () => {
    setError(null);
    setLoading(true);
    try {
      const tasks = getParsedTasks();
      const res = await fetch('/api/evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tasks: tasks && tasks.length > 0 ? tasks : null,
          task_count: currentTaskCount,
          systems: selectedSystems,
          models: selectedModels,
          repeats: currentRepeats,
          seed: Number(seed),
          temperature: Number(temperature),
          dry_run: false,
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to schedule benchmark evaluation');
      }

      const data = await res.json();
      setBenchmarkStarted(data);
      setShowConfirmation(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadPreset300Runs = async () => {
    setTaskCount(20);
    setRepeats(3);
    setSystems({ mas: true, chatdev: true });
    setModels({ 'gpt-4o': true, 'gpt-4o-mini': true });
    setSeed(42);
    setTemperature(0.0);
    try {
      const res = await fetch('/api/evaluations/srdd-tasks');
      if (res.ok) {
        const tasks = await res.json();
        setTaskText(JSON.stringify(tasks, null, 2));
      }
    } catch (e) {
      console.error('Failed to load SRDD tasks:', e);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Layers className="w-6 h-6 text-cyan-400" />
            <span>Batch Benchmark & Empirical Testing</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Execute paired benchmark evaluations under identical model conditions with safety envelopes and dry-run validation.
          </p>
        </div>

        <button
          onClick={loadPreset300Runs}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-mono rounded-lg border border-cyan-800/60 transition-colors flex items-center gap-2"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Load 300-Run Research Matrix Preset</span>
        </button>
      </div>

      {error && (
        <div className="bg-rose-950/70 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {benchmarkStarted && (
        <div className="bg-emerald-950/70 border border-emerald-800 text-emerald-300 p-5 rounded-xl text-xs space-y-2">
          <div className="flex items-center gap-2 font-bold text-sm">
            <CheckCircle2 className="w-5 h-5" />
            <span>Benchmark Evaluation Initiated!</span>
          </div>
          <div>Evaluation ID: <span className="font-mono text-emerald-400">{benchmarkStarted.evaluation_id}</span></div>
          <div>Planned Runs: <span className="font-mono text-emerald-400">{benchmarkStarted.planned_runs}</span></div>
        </div>
      )}

      {/* Input Methods & Configuration */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        {/* Input Method Tabs */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Task Input Source
            </label>
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button
                type="button"
                onClick={() => setInputTab('paste')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                  inputTab === 'paste' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Paste JSON
              </button>
              <button
                type="button"
                onClick={() => setInputTab('json')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                  inputTab === 'json' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Upload JSON
              </button>
              <button
                type="button"
                onClick={() => setInputTab('csv')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                  inputTab === 'csv' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Upload CSV
              </button>
            </div>
          </div>

          {inputTab === 'json' || inputTab === 'csv' ? (
            <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-6 text-center bg-slate-950">
              <Upload className="w-8 h-8 text-slate-500 mx-auto mb-2" />
              <p className="text-xs text-slate-400 mb-2">
                Click to upload your benchmark {inputTab.toUpperCase()} file
              </p>
              <input
                type="file"
                accept={inputTab === 'json' ? '.json' : '.csv'}
                onChange={handleFileUpload}
                className="text-xs text-slate-400"
              />
            </div>
          ) : (
            <textarea
              rows={6}
              value={taskText}
              onChange={(e) => setTaskText(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 focus:border-cyan-500 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none"
            />
          )}
        </div>

        {/* Configuration Matrix */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-2">
          {/* Task count */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
              Task Count
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={taskCount}
              onChange={(e) => setTaskCount(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>

          {/* Repeats */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
              Repeats (Seeds)
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={repeats}
              onChange={(e) => setRepeats(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>

          {/* Seed */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
              Random Seed
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>

          {/* Temperature */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
              Temperature
            </label>
            <input
              type="number"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>
        </div>

        {/* Checkbox Selectors for Systems and Models */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2">
          {/* Systems */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block mb-2">
              Systems to Evaluate
            </span>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={systems.mas}
                  onChange={(e) => setSystems({ ...systems, mas: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span className="font-semibold text-indigo-400">MAS (Proposed Multi-Agent System)</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={systems.chatdev}
                  onChange={(e) => setSystems({ ...systems, chatdev: e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span className="font-semibold text-amber-400">ChatDev (Baseline Benchmark Arm)</span>
              </label>
            </div>
          </div>

          {/* Models */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block mb-2">
              Model Conditions
            </span>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!models['openrouter/free']}
                  onChange={(e) => setModels({ ...models, 'openrouter/free': e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span className="text-emerald-300 font-semibold">openrouter/free (Zero Cost Auto-Router)</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!models['fake']}
                  onChange={(e) => setModels({ ...models, 'fake': e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span className="text-slate-300">FakeLLMProvider (Deterministic Unit Mode)</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!models['gpt-4o']}
                  onChange={(e) => setModels({ ...models, 'gpt-4o': e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span>GPT-4o (Standard Main Benchmark · Paid)</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!models['gpt-4o-mini']}
                  onChange={(e) => setModels({ ...models, 'gpt-4o-mini': e.target.checked })}
                  className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                />
                <span>GPT-4o-mini (Cheaper MAS Arm & Ablations · Paid)</span>
              </label>
            </div>
          </div>
        </div>

        {/* Live Planned Runs & Engineering Envelope Summary */}
        <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl flex flex-wrap items-center justify-between gap-4 font-mono">
          <div className="flex flex-wrap items-center gap-6 text-xs text-slate-300">
            <div>Tasks: <span className="font-bold text-white">{currentTaskCount}</span></div>
            <div>Repeats: <span className="font-bold text-white">{currentRepeats}</span></div>
            <div>Systems: <span className="font-bold text-white">{selectedSystems.length}</span></div>
            <div>Models: <span className="font-bold text-white">{selectedModels.length}</span></div>
            <div className="text-cyan-400 font-bold border-l border-slate-800 pl-4">
              Planned Runs: <span className="text-base text-cyan-300">{plannedRuns}</span>
            </div>
          </div>

          <div className="text-[11px] text-amber-400 bg-amber-950/40 px-3 py-1 rounded border border-amber-800/40">
            ENGINEERING TOKEN ENVELOPE: Budget cap only
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleValidate}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-colors"
            >
              Validate Batch
            </button>
            <button
              type="button"
              onClick={handleDryRun}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold rounded-lg transition-colors"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>Dry Run (0 Model Calls)</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowConfirmation(true)}
            className="flex items-center gap-2 px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg transition-colors shadow-md"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Start Benchmark</span>
          </button>
        </div>
      </div>

      {/* Dry Run Outcome Panel */}
      {dryRunData && (
        <div className="bg-slate-900 border border-teal-800/60 rounded-xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2 text-teal-400 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5" />
              <span>Dry Run Verified (Zero Model Calls Executed)</span>
            </div>
            <span className="text-xs font-mono text-slate-400">
              Evaluation ID: {dryRunData.evaluation_id}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div className="text-slate-400">Planned Runs</div>
              <div className="text-lg font-bold text-cyan-300">{dryRunData.planned_runs}</div>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div className="text-slate-400">Actual Model Calls</div>
              <div className="text-lg font-bold text-emerald-400">0 (Safe Dry Run)</div>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div className="text-slate-400">Token Envelope Cap</div>
              <div className="text-lg font-bold text-amber-300">
                {dryRunData.planning_token_envelope?.total_envelope_millions}M
              </div>
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div className="text-slate-400">Cost Incurred</div>
              <div className="text-lg font-bold text-violet-300">$0.00</div>
            </div>
          </div>

          <div className="p-3 bg-slate-950 rounded-lg border border-amber-900/40 text-[11px] text-amber-400/90 font-mono">
            <strong>{dryRunData.planning_token_envelope?.label}</strong>:
            This envelope represents an engineering upper-bound cap for budget allocation. Actual token counts will come strictly from provider-reported usage returned by the backend upon real execution.
          </div>
        </div>
      )}

      {/* Confirmation Modal (Section D) */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center gap-3 text-amber-400">
              <ShieldAlert className="w-6 h-6" />
              <h2 className="text-base font-bold text-white">Benchmark Configuration Confirmation</h2>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Tasks:</span>
                <span className="text-white font-bold">{currentTaskCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Repeats:</span>
                <span className="text-white font-bold">{currentRepeats}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Systems:</span>
                <span className="text-cyan-400 font-bold">{selectedSystems.join(' + ').toUpperCase()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Models:</span>
                <span className="text-emerald-400 font-bold">{selectedModels.join(', ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Temperature:</span>
                <span className="text-white font-bold">{temperature}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Seed:</span>
                <span className="text-white font-bold">{seed}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-slate-800 text-sm">
                <span className="text-slate-300 font-bold">Expected Runs:</span>
                <span className="text-cyan-300 font-bold">{plannedRuns}</span>
              </div>
            </div>

            {plannedRuns >= 120 && (
              <div className="text-[11px] text-slate-400 bg-indigo-950/40 border border-indigo-800/40 p-3 rounded-lg space-y-1">
                <span className="font-semibold text-indigo-300">300-Run Research Configuration Breakdown:</span>
                <div>• Main: 20 tasks × 3 repeats × MAS/ChatDev × GPT-4o = 120</div>
                <div>• MAS cheaper-model: 20 × 3 × GPT-4o-mini = 60</div>
                <div>• Ablations: 10 × 2 × 6 × GPT-4o-mini = 120</div>
                <div>• Total Core Runs: 300 runs</div>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => setShowConfirmation(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmStart}
                disabled={loading}
                className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded-lg transition-colors shadow-lg"
              >
                {loading ? 'Submitting...' : 'CONFIRM & START BENCHMARK'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
