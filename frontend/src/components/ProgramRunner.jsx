import React, { useState } from 'react';
import { Play, MonitorUp, Loader2, CheckCircle2, XCircle, Info } from 'lucide-react';

// "Run Program" tab (DEC-053): test-run the generated project, or open it on this computer.
export default function ProgramRunner({ runId }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);
  const [opening, setOpening] = useState(false);
  const [openInfo, setOpenInfo] = useState(null);
  const [args, setArgs] = useState('');
  const [error, setError] = useState(null);

  const post = async (url, body) => {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `The server returned status ${res.status}`);
    return data;
  };

  const runTest = async () => {
    setTesting(true);
    setError(null);
    setResult(null);
    try {
      setResult(await post(`/api/runs/${encodeURIComponent(runId)}/quick-test`));
    } catch (e) {
      setError(e.message);
    } finally {
      setTesting(false);
    }
  };

  const openProgram = async () => {
    setOpening(true);
    setError(null);
    setOpenInfo(null);
    try {
      setOpenInfo(await post(`/api/runs/${encodeURIComponent(runId)}/open`, { args }));
    } catch (e) {
      setError(e.message);
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-800 rounded-lg p-5 flex flex-col">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Play className="w-4 h-4 text-cyan-500" />
            Quick test
          </div>
          <p className="text-xs text-slate-500 mt-1 flex-1">
            Runs the program the same way the scoring did: no keyboard input, windows closed straight away, 45-second limit.
            The output appears below.
          </p>
          <button
            onClick={runTest}
            disabled={testing}
            className="mt-4 self-start flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-white rounded-md text-sm font-semibold"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {testing ? 'Running…' : 'Run quick test'}
          </button>
        </div>

        <div className="bg-white border border-slate-800 rounded-lg p-5 flex flex-col">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <MonitorUp className="w-4 h-4 text-cyan-500" />
            Open on this computer
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Starts the program in a new console window so you can use it: type answers, or see its window if it has one.
          </p>
          <label className="text-xs text-slate-400 mt-3 mb-1">Command-line arguments (optional)</label>
          <input
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            placeholder="e.g. --help"
            className="w-full bg-white border border-slate-700 focus:border-cyan-500 rounded-md px-3 py-1.5 text-sm text-slate-200 focus:outline-none"
          />
          <button
            onClick={openProgram}
            disabled={opening}
            className="mt-3 self-start flex items-center gap-2 px-4 py-2 bg-white border border-slate-700 hover:bg-slate-925 disabled:opacity-60 text-slate-200 rounded-md text-sm font-semibold"
          >
            {opening ? <Loader2 className="w-4 h-4 animate-spin" /> : <MonitorUp className="w-4 h-4" />}
            Open program
          </button>
        </div>
      </div>

      <div className="text-xs text-slate-500 flex gap-2">
        <Info className="w-4 h-4 flex-shrink-0" />
        <span>
          Both options run a temporary copy, so the saved benchmark files are never changed, and the program never sees
          your API key. Nothing here changes any score.
        </span>
      </div>

      {error && <div className="bg-rose-950 border border-rose-800 text-rose-300 p-3 rounded-lg text-sm">{error}</div>}

      {openInfo && (
        <div className="bg-emerald-950 border border-emerald-800 text-emerald-300 p-3 rounded-lg text-sm">
          Opened <code>{openInfo.entry_point}</code>
          {openInfo.args?.length ? ` with ${openInfo.args.join(' ')}` : ''} in a new window. Look for it on your taskbar.
        </div>
      )}

      {result && (
        <div className="bg-white border border-slate-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
            {result.success ? (
              <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                <CheckCircle2 className="w-4 h-4" /> Ran without error
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-rose-400 font-semibold">
                <XCircle className="w-4 h-4" /> {result.timed_out ? 'Did not finish within the time limit' : 'Stopped with an error'}
              </span>
            )}
            <span className="text-slate-500">
              File: <span className="text-slate-300">{result.entry_point || '-'}</span>
            </span>
            <span className="text-slate-500">
              Exit code: <span className="text-slate-300">{result.exit_code ?? '-'}</span>
            </span>
            <span className="text-slate-500">
              Time: <span className="text-slate-300">{((result.duration_ms || 0) / 1000).toFixed(1)}s</span>
            </span>
          </div>
          <div className="p-4 space-y-3">
            <div>
              <div className="text-xs text-slate-500 mb-1">Program output</div>
              <pre className="bg-slate-925 border border-slate-800 rounded-md p-3 text-xs text-slate-200 max-h-80 overflow-auto whitespace-pre-wrap">
                {result.stdout || '(no output)'}
              </pre>
            </div>
            {result.stderr && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Errors and warnings</div>
                <pre className="bg-rose-950 border border-rose-800 rounded-md p-3 text-xs text-rose-300 max-h-80 overflow-auto whitespace-pre-wrap">
                  {result.stderr}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
