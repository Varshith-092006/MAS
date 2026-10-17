import React, { useState, useEffect } from 'react';
import {
  Folder,
  FileCode,
  FileText,
  Copy,
  Check,
  Download,
  RefreshCw,
  Loader2,
  Terminal,
  Code2,
} from 'lucide-react';

export default function WorkspaceExplorer({ runId }) {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [copied, setCopied] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');

  const fetchFileList = async () => {
    if (!runId) return;
    setLoadingList(true);
    try {
      const res = await fetch(`/api/runs/${runId}/workspace`);
      if (res.ok) {
        const data = await res.json();
        const list = data.files || [];
        setFiles(list);
        if (list.length > 0 && !selectedFile) {
          fetchFileContent(list[0].path);
        }
      }
    } catch (err) {
      console.error('Error fetching workspace files:', err);
    } finally {
      setLoadingList(false);
    }
  };

  const fetchFileContent = async (filePath) => {
    setSelectedFile(filePath);
    setLoadingContent(true);
    try {
      const res = await fetch(`/api/runs/${runId}/workspace?file_path=${encodeURIComponent(filePath)}`);
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content || '');
      } else {
        setFileContent('# Could not load file content');
      }
    } catch (err) {
      setFileContent(`# Error: ${err.message}`);
    } finally {
      setLoadingContent(false);
    }
  };

  useEffect(() => {
    fetchFileList();
  }, [runId]);

  const handleCopy = () => {
    if (!fileContent) return;
    navigator.clipboard.writeText(fileContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!fileContent || !selectedFile) return;
    const blob = new Blob([fileContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedFile.split('/').pop() || 'file.py';
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredFiles = files.filter((f) =>
    f.path.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-hidden flex flex-col h-[640px]">
      {/* Top Header */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-950/60">
        <div className="flex items-center gap-2">
          <Code2 className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-bold text-white">Generated Project Workspace</h3>
          <span className="text-xs font-mono text-slate-400">
            ({files.length} {files.length === 1 ? 'file' : 'files'})
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchFileList}
            disabled={loadingList}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors text-xs flex items-center gap-1.5 px-2.5"
            title="Refresh file list"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingList ? 'animate-spin text-cyan-400' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main split view: File list (left) & Code viewer (right) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left pane: File tree */}
        <div className="w-64 border-r border-slate-800 flex flex-col bg-slate-950/40">
          <div className="p-2.5 border-b border-slate-800">
            <input
              type="text"
              placeholder="Filter files..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {loadingList ? (
              <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                <span>Reading files...</span>
              </div>
            ) : filteredFiles.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500 italic">
                {files.length === 0 ? 'No files generated in workspace yet.' : 'No files matching query.'}
              </div>
            ) : (
              filteredFiles.map((f) => {
                const isSelected = selectedFile === f.path;
                const isPython = f.name.endsWith('.py');
                return (
                  <button
                    key={f.path}
                    onClick={() => fetchFileContent(f.path)}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center justify-between transition-colors ${
                      isSelected
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {isPython ? (
                        <FileCode className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                      ) : (
                        <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                      )}
                      <span className="truncate">{f.path}</span>
                    </div>
                    <span className="text-[10px] text-slate-600 ml-1">
                      {f.size ? `${Math.round(f.size / 1024 * 10) / 10}KB` : ''}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right pane: Code viewer */}
        <div className="flex-1 flex flex-col bg-slate-950">
          {selectedFile ? (
            <>
              {/* File bar */}
              <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-mono font-bold text-slate-200">{selectedFile}</span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    className="p-1 px-2 text-[11px] font-mono rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors flex items-center gap-1.5"
                    title="Copy code"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3 text-slate-400" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={handleDownload}
                    className="p-1 px-2 text-[11px] font-mono rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors flex items-center gap-1.5"
                    title="Download file"
                  >
                    <Download className="w-3 h-3 text-slate-400" />
                    <span>Download</span>
                  </button>
                </div>
              </div>

              {/* Code text */}
              <div className="flex-1 overflow-auto p-4 font-mono text-xs text-slate-200 leading-relaxed bg-slate-950">
                {loadingContent ? (
                  <div className="flex items-center justify-center h-full text-slate-500 gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
                    <span>Loading file content...</span>
                  </div>
                ) : (
                  <pre className="overflow-x-auto select-text font-mono">
                    <code>
                      {fileContent.split('\n').map((line, idx) => (
                        <div key={idx} className="table-row hover:bg-slate-900/60">
                          <span className="table-cell select-none pr-4 text-right text-slate-600 text-[11px] w-10 font-mono">
                            {idx + 1}
                          </span>
                          <span className="table-cell whitespace-pre">{line || ' '}</span>
                        </div>
                      ))}
                    </code>
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 p-8 text-center">
              <Folder className="w-12 h-12 text-slate-700 mb-2 stroke-[1.5]" />
              <p className="text-xs">Select a generated file from the list to preview code and dependencies.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
