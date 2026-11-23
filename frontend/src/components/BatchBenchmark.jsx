import React, { useState, useEffect } from 'react';
import { ListChecks, Upload, CheckCircle2, AlertTriangle, Play, Loader2, Info } from 'lucide-react';

const OFFLINE = 'fake';

const SAMPLE_TASKS = [
  { task_id: 'task_001', requirement: 'Build a calculator application with add, subtract, multiply, and divide functions.', category: 'Creation' },
  { task_id: 'task_002', requirement: 'Build a personal expense tracker with budget categories and monthly summaries.', category: 'Life' },
  { task_id: 'task_003', requirement: 'Build a flashcard study tool with spaced repetition intervals.', category: 'Education' },
];

export default function BatchBenchmark() {
  const [taskText, setTaskText] = useState(JSON.stringify(SAMPLE_TASKS, null, 2));
  const [repeats, setRepeats] = useState(1);
  const [systems, setSystems] = useState({ mas: true, chatdev: true });
  const [model, setModel] = useState(OFFLINE);
  const [config, setConfig] = useState(null);
  const [seed, setSeed] = useState(42);
  const [temperature, setTemperature] = useState(0.0);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [preview, setPreview] = useState(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [started, setStarted] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/config')
      .then((r) => (r.ok ? r.json() : null))
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const liveModel = config?.bench_model || null;
  const liveReady = Boolean(liveModel && config?.api_key_configured);

  const parseTasks = () => {
    try {
      const text = taskText.trim();
      if (!text.startsWith('[')) {
        // CSV: task_id,requirement,category (first line is the header)
        const lines = text.split('\n').slice(1).filter(Boolean);
        return lines.map((line, idx) => {
          const parts = line.split(',');
          return {
            task_id: parts[0]?.trim() || `task_${String(idx + 1).padStart(3, '0')}`,
            requirement: parts.slice(1, -1).join(',').trim() || parts[1]?.trim() || '',
            category: parts[parts.length - 1]?.trim() || 'Creation',
          };
        });
      }
      const parsed = JSON.parse(text);
      return Array.isArray(parsed) ? parsed : null;
    } catch (e) {
      return null;
    }
  };

  const tasks = parseTasks();
  const taskCount = tasks ? tasks.length : 0;
  const selectedSystems = Object.keys(systems).filter((k) => systems[k]);
  const currentRepeats = Number(repeats) || 1;
  const plannedRuns = taskCount * currentRepeats * selectedSystems.length;
  const canRun = taskCount > 0 && selectedSystems.length > 0;

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => setTaskText(event.target.result);
    reader.readAsText(file);
  };

  const loadBenchmarkTasks = async () => {
    setError(null);
    try {
      const res = await fetch('/api/evaluations/srdd-tasks');
      if (!res.ok) throw new Error(`Could not load the benchmark tasks (${res.status})`);
      setTaskText(JSON.stringify(await res.json(), null, 2));
    } catch (e) {
      setError(e.message);
    }
  };

  const submit = async (dryRun) => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch('/api/evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tasks,
          task_count: taskCount,
          systems: selectedSystems,
          models: [model],
          repeats: currentRepeats,
          seed: Number(seed),
          temperature: Number(temperature),
          dry_run: dryRun,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `The server returned status ${res.status}`);
      }
      const data = await res.json();
      if (dryRun) setPreview(data);
      else {
        setStarted(data);
        setShowConfirmation(false);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const label = 'block text-sm font-semibold text-slate-200 mb-2';
  const input = 'w-full bg-white border border-slate-700 focus:border-cyan-500 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none';
  const choiceClass = (active) =>
    `py-2.5 px-3 rounded-md text-sm border text-left transition-colors ${
      active ? 'bg-cyan-950 border-cyan-500 text-cyan-400 font-semibold' : 'bg-white border-slate-700 text-slate-300 hover:bg-slate-925'
    }`;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
          <ListChecks className="w-6 h-6 text-cyan-500" />
          <span>Run a Benchmark</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Run a list of tasks on MAS and ChatDev under the same model and settings, then compare their scores.
        </p>
      </div>

      <div className="bg-cyan-950 border border-cyan-800 text-slate-300 p-3 rounded-lg text-xs flex gap-2">
        <Info className="w-4 h-4 text-cyan-500 flex-shrink-0 mt-0.5" />
        <span>
          The final results in the report were produced with the command-line runner
          (<code>python -m eval.runner --benchmark …</code>), which stops at the daily API limit and resumes the next day.
          Use this page for small trial batches.
        </span>
      </div>

      {error && (
        <div className="bg-rose-950 border border-rose-800 text-rose-300 p-4 rounded-lg text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {started && (
        <div className="bg-emerald-950 border border-emerald-800 text-emerald-300 p-4 rounded-lg text-sm">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="w-5 h-5" />
            <span>Benchmark started</span>
          </div>
          <div className="text-xs mt-1">
            Batch {started.evaluation_id} · {started.planned_runs} runs planned. Results appear under All Runs as they finish.
          </div>
        </div>
      )}

      <div className="bg-white border border-slate-800 rounded-lg p-6 space-y-6">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <span className="text-sm font-semibold text-slate-200">1. Tasks</span>
            <div className="flex items-center gap-2">
              <button type="button" onClick={loadBenchmarkTasks} className="px-3 py-1.5 border border-slate-700 rounded-md text-xs text-slate-300 hover:bg-slate-925">
                Load the 20 benchmark tasks
              </button>
              <label className="px-3 py-1.5 border border-slate-700 rounded-md text-xs text-slate-300 hover:bg-slate-925 cursor-pointer flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5" />
                Upload JSON or CSV
                <input type="file" accept=".json,.csv" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>
          </div>
          <textarea
            rows={7}
            value={taskText}
            onChange={(e) => setTaskText(e.target.value)}
            className={`${input} font-mono text-xs`}
          />
          <div className={`text-xs mt-1 ${tasks ? 'text-slate-500' : 'text-rose-400'}`}>
            {tasks
              ? `${taskCount} task${taskCount === 1 ? '' : 's'} found. Each task needs task_id, requirement and category.`
              : 'Could not read the tasks. Use a JSON list, or CSV with the header task_id,requirement,category.'}
          </div>
        </div>

        <div>
          <span className={label}>2. Systems to compare</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[
              ['mas', 'MAS', 'Our multi-agent system'],
              ['chatdev', 'ChatDev', 'The baseline we compare against'],
            ].map(([id, name, hint]) => (
              <label key={id} className={`${choiceClass(systems[id])} flex items-start gap-2 cursor-pointer`}>
                <input
                  type="checkbox"
                  checked={systems[id]}
                  onChange={(e) => setSystems({ ...systems, [id]: e.target.checked })}
                  className="mt-1"
                />
                <span>
                  {name}
                  <span className="block text-xs font-normal text-slate-500">{hint}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <span className={label}>3. AI model</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button type="button" onClick={() => setModel(OFFLINE)} className={choiceClass(model === OFFLINE)}>
              Offline test mode
              <span className="block text-xs font-normal text-slate-500">No API calls. For trying the pipeline.</span>
            </button>
            <button
              type="button"
              disabled={!liveReady}
              onClick={() => liveReady && setModel(liveModel)}
              className={`${choiceClass(model === liveModel && liveReady)} disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              Live model{liveModel ? `: ${liveModel}` : ''}
              <span className="block text-xs font-normal text-slate-500">
                {liveReady ? 'Uses your daily API quota.' : 'Not set up in .env.'}
              </span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <span className={label}>4. Repeats per task</span>
            <input type="number" min={1} max={10} value={repeats} onChange={(e) => setRepeats(e.target.value)} className={input} />
          </div>
          <div className="sm:col-span-2 flex items-end">
            <button type="button" onClick={() => setShowAdvanced(!showAdvanced)} className="text-xs text-cyan-400 hover:underline pb-2">
              {showAdvanced ? 'Hide advanced settings' : 'Show advanced settings (seed, temperature)'}
            </button>
          </div>
          {showAdvanced && (
            <>
              <div>
                <span className={label}>Seed</span>
                <input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} className={input} />
              </div>
              <div>
                <span className={label}>Temperature</span>
                <input type="number" step="0.1" value={temperature} onChange={(e) => setTemperature(e.target.value)} className={input} />
              </div>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-800">
          <div className="text-sm text-slate-300">
            {taskCount} tasks × {currentRepeats} repeat{currentRepeats === 1 ? '' : 's'} × {selectedSystems.length} system
            {selectedSystems.length === 1 ? '' : 's'} = <span className="font-semibold text-slate-100">{plannedRuns} runs</span>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => submit(true)}
              disabled={loading || !canRun}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-700 hover:bg-slate-925 disabled:opacity-50 text-slate-200 text-sm font-semibold rounded-md"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Preview plan (no API calls)
            </button>
            <button
              type="button"
              onClick={() => setShowConfirmation(true)}
              disabled={!canRun}
              className="flex items-center gap-2 px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-sm font-semibold rounded-md"
            >
              <Play className="w-4 h-4" />
              Start benchmark
            </button>
          </div>
        </div>
      </div>

      {preview && (
        <div className="bg-white border border-slate-800 rounded-lg p-5 space-y-3">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
            <CheckCircle2 className="w-5 h-5" />
            <span>Plan checked. Nothing was sent to the model.</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div className="bg-slate-925 p-3 rounded-md border border-slate-800">
              <div className="text-xs text-slate-500">Runs planned</div>
              <div className="text-lg font-semibold text-slate-100">{preview.planned_runs}</div>
            </div>
            <div className="bg-slate-925 p-3 rounded-md border border-slate-800">
              <div className="text-xs text-slate-500">Model calls made</div>
              <div className="text-lg font-semibold text-slate-100">0</div>
            </div>
            <div className="bg-slate-925 p-3 rounded-md border border-slate-800">
              <div className="text-xs text-slate-500">Token limit for this plan</div>
              <div className="text-lg font-semibold text-slate-100">
                {preview.planning_token_envelope?.total_envelope_millions != null
                  ? `${preview.planning_token_envelope.total_envelope_millions}M`
                  : '-'}
              </div>
            </div>
          </div>
          <p className="text-xs text-slate-500">
            The token limit is a safety ceiling, not an estimate. Real token counts come from the provider after each run.
          </p>
        </div>
      )}

      {showConfirmation && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-800 rounded-lg max-w-md w-full p-6 space-y-4">
            <h2 className="text-base font-semibold text-slate-100">Start this benchmark?</h2>
            <div className="bg-slate-925 p-4 rounded-md border border-slate-800 text-sm space-y-1.5">
              <div className="flex justify-between"><span className="text-slate-500">Tasks</span><span>{taskCount}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Repeats</span><span>{currentRepeats}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Systems</span><span>{selectedSystems.map((s) => (s === 'mas' ? 'MAS' : 'ChatDev')).join(', ')}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Model</span><span>{model === OFFLINE ? 'Offline test mode' : model}</span></div>
              <div className="flex justify-between pt-2 border-t border-slate-800 font-semibold"><span>Total runs</span><span>{plannedRuns}</span></div>
            </div>
            {model !== OFFLINE && (
              <p className="text-xs text-amber-400">
                This uses the live model and counts against the daily API quota.
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowConfirmation(false)} className="px-4 py-2 border border-slate-700 text-slate-300 text-sm rounded-md hover:bg-slate-925">
                Cancel
              </button>
              <button
                type="button"
                onClick={() => submit(false)}
                disabled={loading}
                className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold rounded-md"
              >
                {loading ? 'Starting…' : 'Start'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
