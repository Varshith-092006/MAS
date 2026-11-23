import React from 'react';
import {
  LayoutDashboard,
  Wand2,
  ListChecks,
  TableProperties,
  FileSearch,
  BarChart3,
  Scale,
  BookOpen,
  Activity,
  Boxes,
} from 'lucide-react';

// Plain-language navigation (DEC-051). Each item maps to one URL in App.jsx.
export default function Sidebar({ activePage, onNavigate, lastRunId }) {
  const navGroups = [
    {
      label: null,
      items: [{ id: 'overview', label: 'Overview', hint: 'Summary of all runs', icon: LayoutDashboard }],
    },
    {
      label: 'Create',
      items: [
        { id: 'generate', label: 'Generate a Project', hint: 'Turn one requirement into code', icon: Wand2 },
        { id: 'benchmark', label: 'Run a Benchmark', hint: 'Test many tasks at once', icon: ListChecks },
      ],
    },
    {
      label: 'Results',
      items: [
        { id: 'runs', label: 'All Runs', hint: 'Every run and its scores', icon: TableProperties },
        {
          id: 'run',
          label: 'Run Details',
          hint: lastRunId ? 'Last opened run' : 'Open a run from All Runs',
          icon: FileSearch,
          disabled: !lastRunId,
        },
        { id: 'charts', label: 'Scores & Charts', hint: 'Averages and token use', icon: BarChart3 },
        { id: 'compare', label: 'Compare Systems', hint: 'MAS vs ChatDev vs single agent', icon: Scale },
      ],
    },
    {
      label: 'Reference',
      items: [{ id: 'paper', label: 'Paper Results', hint: 'Published iCoder numbers', icon: BookOpen }],
    },
    {
      label: 'System',
      items: [{ id: 'status', label: 'System Status', hint: 'Backend, model and settings', icon: Activity }],
    },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-800 flex flex-col flex-shrink-0 min-h-screen">
      <div className="px-5 py-4 border-b border-slate-800">
        <button onClick={() => onNavigate('overview')} className="flex items-center gap-3 text-left">
          <div className="w-9 h-9 rounded-lg bg-cyan-600 flex items-center justify-center text-white flex-shrink-0">
            <Boxes style={{ width: '18px', height: '18px' }} />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-100 leading-tight">MAS</div>
            <div className="text-xs text-slate-500 leading-tight mt-0.5">Multi-Agent Code Generator</div>
          </div>
        </button>
      </div>

      <nav className="p-3 space-y-4 flex-1 overflow-y-auto">
        {navGroups.map((group, gi) => (
          <div key={group.label || gi}>
            {group.label && (
              <div className="px-3 mb-1 text-[11px] font-semibold uppercase text-slate-500">{group.label}</div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activePage === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => !item.disabled && onNavigate(item.id)}
                    disabled={item.disabled}
                    title={item.hint}
                    className={`w-full flex items-start gap-2.5 px-3 py-2 rounded-md text-left transition-colors duration-100 ${
                      isActive
                        ? 'bg-cyan-950 text-cyan-400'
                        : item.disabled
                        ? 'text-slate-600 cursor-not-allowed'
                        : 'text-slate-300 hover:bg-slate-850'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isActive ? 'text-cyan-500' : 'text-slate-500'}`} />
                    <span className="min-w-0">
                      <span className={`block text-[13px] leading-tight ${isActive ? 'font-semibold' : 'font-medium'}`}>
                        {item.label}
                      </span>
                      <span className="block text-[11px] text-slate-500 leading-tight mt-0.5 truncate">{item.hint}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-5 py-3 border-t border-slate-800 text-[11px] text-slate-500">
        Final Year Project · v0.1.0
      </div>
    </aside>
  );
}
