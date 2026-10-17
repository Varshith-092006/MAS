import React, { useState, useEffect } from 'react';
import {
  Boxes,
  Layers,
  FileCheck,
  CheckCircle2,
  AlertCircle,
  FileCode,
  Sparkles,
  RefreshCw,
  Loader2,
  ChevronRight,
  Code,
  ShieldAlert,
} from 'lucide-react';

export default function ArtifactsInspector({ runId }) {
  const [artifacts, setArtifacts] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchArtifacts = async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/runs/${runId}/artifacts`);
      if (res.ok) {
        const data = await res.json();
        setArtifacts(data || []);
      } else {
        setError('Failed to fetch artifacts.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, [runId]);

  const activeArt = artifacts[selectedIdx] || null;

  const renderArtifactView = (art) => {
    if (!art) return null;
    const type = art.type;
    const data = art.json_data || {};

    switch (type) {
      case 'Architecture':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-indigo-900/40">
              <div className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-1">
                Architecture Overview & Rationale
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {data.rationale || data.overview || 'System architecture and component decomposition.'}
              </p>
            </div>

            {data.uml_classes && data.uml_classes.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  UML Class Model Specifications ({data.uml_classes.length} Classes)
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {data.uml_classes.map((cls, idx) => (
                    <div key={idx} className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                        <span className="font-mono font-bold text-cyan-400 text-xs">
                          class {cls.name || cls.class_name}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {cls.module || 'module'}
                        </span>
                      </div>
                      {cls.methods && cls.methods.length > 0 && (
                        <div className="space-y-1 font-mono text-[11px] text-slate-300">
                          <span className="text-slate-500 text-[10px] block">Methods:</span>
                          {cls.methods.map((m, mIdx) => (
                            <div key={mIdx} className="text-emerald-400/90 pl-2">
                              + {typeof m === 'string' ? m : `${m.name}(${m.args || ''}): ${m.return_type || 'None'}`}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.dependencies && (
              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 text-xs font-mono">
                <span className="text-slate-500 text-[10px] block mb-1">Inter-Module Dependencies:</span>
                <pre className="text-slate-300 overflow-x-auto">
                  {JSON.stringify(data.dependencies, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );

      case 'TaskPlan':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-cyan-900/40">
              <div className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-1">
                Normalized Scope & Execution Strategy
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {data.plan_summary || data.description || 'Normalized tasks planned for development.'}
              </p>
              {data.complexity && (
                <div className="mt-2 text-xs font-mono">
                  <span className="text-slate-500">Router Classification: </span>
                  <span className="text-cyan-300 font-bold uppercase">{data.complexity}</span>
                </div>
              )}
            </div>

            {data.tasks && data.tasks.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Planned Execution Units ({data.tasks.length})
                </div>
                <div className="space-y-2">
                  {data.tasks.map((task, idx) => (
                    <div key={idx} className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex items-start gap-3">
                      <span className="text-cyan-400 font-mono font-bold text-xs">
                        #{idx + 1}
                      </span>
                      <div className="flex-1 text-xs space-y-1">
                        <div className="font-semibold text-slate-200">
                          {task.title || task.name || `Task ${idx + 1}`}
                        </div>
                        <div className="text-slate-400 text-[11px]">
                          {task.description || JSON.stringify(task)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );

      case 'UserStory':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-purple-900/40 space-y-2">
              <div className="text-xs font-bold text-purple-400 uppercase tracking-wider">
                User Personas & Functional Scenarios
              </div>
              <div className="text-xs text-slate-300">
                <span className="font-semibold text-slate-200">As a: </span>
                {data.persona || data.role || 'End User'}
              </div>
              <div className="text-xs text-slate-300">
                <span className="font-semibold text-slate-200">I want to: </span>
                {data.action || data.goal || 'accomplish task objectives'}
              </div>
              <div className="text-xs text-slate-300">
                <span className="font-semibold text-slate-200">So that: </span>
                {data.benefit || data.value || 'requirements are satisfied deterministically.'}
              </div>
            </div>

            {data.acceptance_criteria && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Acceptance Criteria
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1.5 font-mono text-xs">
                  {Array.isArray(data.acceptance_criteria) ? (
                    data.acceptance_criteria.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 text-slate-300">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                        <span>{typeof c === 'string' ? c : JSON.stringify(c)}</span>
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-300">{String(data.acceptance_criteria)}</div>
                  )}
                </div>
              </div>
            )}
          </div>
        );

      case 'CodePatch':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-emerald-900/40">
              <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-1">
                Developer Agent Code Synthesis
              </div>
              <div className="text-xs text-slate-300">
                {data.commit_message || data.summary || 'Code patch applied to workspace repository.'}
              </div>
            </div>

            {data.files && Object.keys(data.files).length > 0 && (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Modified File Units ({Object.keys(data.files).length})
                </div>
                {Object.entries(data.files).map(([fname, fcontent], idx) => (
                  <div key={idx} className="bg-slate-950 rounded-lg border border-slate-800 overflow-hidden">
                    <div className="bg-slate-900 px-3 py-1.5 border-b border-slate-800 flex items-center justify-between text-xs font-mono text-slate-200">
                      <div className="flex items-center gap-2">
                        <FileCode className="w-3.5 h-3.5 text-emerald-400" />
                        <span>{fname}</span>
                      </div>
                    </div>
                    <pre className="p-3 text-xs font-mono text-slate-300 overflow-x-auto max-h-60 leading-relaxed">
                      {typeof fcontent === 'string' ? fcontent : JSON.stringify(fcontent, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'ReviewReport':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-violet-900/40 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-violet-400 uppercase tracking-wider">
                  Semantic Code Review
                </div>
                <div className="text-sm font-semibold text-slate-200 mt-1">
                  Status: {data.approved ? 'APPROVED' : 'CHANGES REQUESTED'}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-slate-500 font-mono">Review Score</div>
                <div className="text-xl font-bold font-mono text-violet-300">
                  {data.score !== undefined ? data.score.toFixed(2) : '1.00'}
                </div>
              </div>
            </div>

            {data.comments && (
              <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-xs text-slate-300 leading-relaxed">
                <span className="font-bold text-slate-400 block mb-1">Review Feedback:</span>
                {Array.isArray(data.comments) ? (
                  <ul className="list-disc pl-4 space-y-1">
                    {data.comments.map((c, i) => (
                      <li key={i}>{typeof c === 'string' ? c : JSON.stringify(c)}</li>
                    ))}
                  </ul>
                ) : (
                  <div>{String(data.comments)}</div>
                )}
              </div>
            )}
          </div>
        );

      case 'TestReport':
        return (
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-xl border border-teal-900/40 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-teal-400 uppercase tracking-wider">
                  Internal Test Report
                </div>
                <div className="text-sm font-semibold text-slate-200 mt-1">
                  Passed: {data.passed_tests || 0} / {data.total_tests || 0} tests
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-slate-500 font-mono">Pass Rate</div>
                <div className="text-xl font-bold font-mono text-teal-300">
                  {data.pass_rate !== undefined ? `${(data.pass_rate * 100).toFixed(1)}%` : '100%'}
                </div>
              </div>
            </div>

            {data.failures && data.failures.length > 0 && (
              <div className="bg-rose-950/40 p-4 rounded-lg border border-rose-900/60 text-xs text-rose-300 space-y-1">
                <div className="font-bold flex items-center gap-1.5 text-rose-400">
                  <ShieldAlert className="w-4 h-4" />
                  <span>Test Failures:</span>
                </div>
                {data.failures.map((f, i) => (
                  <div key={i} className="font-mono text-[11px]">{typeof f === 'string' ? f : JSON.stringify(f)}</div>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return (
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
            <pre>{JSON.stringify(data, null, 2)}</pre>
          </div>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-hidden flex flex-col h-[640px]">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center gap-2">
          <Boxes className="w-5 h-5 text-indigo-400" />
          <h3 className="text-sm font-bold text-white">Inter-Agent Artifact Inspector</h3>
          <span className="text-xs font-mono text-slate-400">
            ({artifacts.length} {artifacts.length === 1 ? 'artifact' : 'artifacts'})
          </span>
        </div>

        <button
          onClick={fetchArtifacts}
          disabled={loading}
          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors text-xs flex items-center gap-1.5 px-2.5"
          title="Refresh artifacts"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Main split */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left pane: Artifact list */}
        <div className="w-64 border-r border-slate-800 p-2 space-y-1.5 bg-slate-950/40 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              <span>Loading artifacts...</span>
            </div>
          ) : artifacts.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-500 italic">
              No artifacts recorded for this run yet.
            </div>
          ) : (
            artifacts.map((art, idx) => {
              const isSelected = selectedIdx === idx;
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedIdx(idx)}
                  className={`w-full text-left p-2.5 rounded-lg text-xs font-mono transition-colors flex items-center justify-between ${
                    isSelected
                      ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  <div className="truncate">
                    <div className="font-bold">{art.type}</div>
                    <div className="text-[10px] text-slate-500">v{art.version || 1} • {art.schema_valid ? 'Schema Valid' : 'Invalid'}</div>
                  </div>
                  <ChevronRight className={`w-4 h-4 ${isSelected ? 'text-indigo-400' : 'text-slate-600'}`} />
                </button>
              );
            })
          )}
        </div>

        {/* Right pane: Active artifact viewer */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-950">
          {activeArt ? (
            <div className="space-y-4 max-w-4xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-white font-mono">
                    {activeArt.type}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                    Schema Validated
                  </span>
                </div>
                <span className="text-xs font-mono text-slate-500">
                  Version {activeArt.version || 1}
                </span>
              </div>

              {renderArtifactView(activeArt)}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 text-xs">
              <Layers className="w-10 h-10 text-slate-700 mb-2 stroke-[1.5]" />
              <p>Select an artifact to inspect its schema and structure.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
