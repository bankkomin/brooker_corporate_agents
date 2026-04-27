"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import {
  Database,
  FolderOpen,
  FileText,
  HardDrive,
  BookOpen,
  Table2,
  Upload,
  CheckCircle2,
  XCircle,
  Loader2,
  File as FileIcon,
  X,
  ArrowRight,
  MessageSquare,
  FileSpreadsheet,
  Globe,
  Pencil,
  ShieldCheck,
} from "lucide-react";
import { getDepartment } from "@/lib/departments";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";

/* ------------------------------------------------------------------ */
/*  Static config                                                      */
/* ------------------------------------------------------------------ */

const VAULT_FOLDERS: {
  path: string;
  collection: string;
  docType: string;
  dept: string;
}[] = [
  { path: "shared/policies/",             collection: "shared_policies",  docType: "Policy Note",   dept: "shared" },
  { path: "shared/escalation-protocols/", collection: "shared_policies",  docType: "Escalation",    dept: "shared" },
  { path: "cac/concepts/",               collection: "cac_knowledge",    docType: "Concept",       dept: "cac" },
  { path: "cac/decisions/",              collection: "cac_knowledge",    docType: "Decision Log",  dept: "cac" },
  { path: "cac/meeting-notes/",          collection: "cac_knowledge",    docType: "Meeting Note",  dept: "cac" },
  { path: "cac/entities/",               collection: "cac_knowledge",    docType: "Entity",        dept: "cac" },
  { path: "cac/trends/",                 collection: "cac_knowledge",    docType: "Trend",         dept: "cac" },
  { path: "hr/concepts/",                collection: "hr_knowledge",     docType: "Concept",       dept: "hr" },
  { path: "hr/decisions/",               collection: "hr_knowledge",     docType: "Decision Log",  dept: "hr" },
  { path: "hr/meeting-notes/",           collection: "hr_knowledge",     docType: "Meeting Note",  dept: "hr" },
  { path: "hr/entities/",                collection: "hr_knowledge",     docType: "Entity",        dept: "hr" },
  { path: "risk/concepts/",              collection: "risk_knowledge",   docType: "Concept",       dept: "risk" },
  { path: "risk/decisions/",             collection: "risk_knowledge",   docType: "Decision Log",  dept: "risk" },
  { path: "risk/meeting-notes/",         collection: "risk_knowledge",   docType: "Meeting Note",  dept: "risk" },
  { path: "risk/entities/",              collection: "risk_knowledge",   docType: "Entity",        dept: "risk" },
  { path: "legal/concepts/",             collection: "legal_knowledge",  docType: "Concept",       dept: "legal" },
  { path: "legal/decisions/",            collection: "legal_knowledge",  docType: "Decision Log",  dept: "legal" },
  { path: "legal/meeting-notes/",        collection: "legal_knowledge",  docType: "Meeting Note",  dept: "legal" },
  { path: "legal/entities/",             collection: "legal_knowledge",  docType: "Entity",        dept: "legal" },
  { path: "invest/concepts/",            collection: "invest_knowledge", docType: "Concept",       dept: "invest" },
  { path: "invest/decisions/",           collection: "invest_knowledge", docType: "Decision Log",  dept: "invest" },
  { path: "invest/meeting-notes/",       collection: "invest_knowledge", docType: "Meeting Note",  dept: "invest" },
  { path: "invest/entities/",            collection: "invest_knowledge", docType: "Entity",        dept: "invest" },
  { path: "ops/concepts/",               collection: "ops_knowledge",    docType: "Concept",       dept: "ops" },
  { path: "ops/decisions/",              collection: "ops_knowledge",    docType: "Decision Log",  dept: "ops" },
  { path: "ops/meeting-notes/",          collection: "ops_knowledge",    docType: "Meeting Note",  dept: "ops" },
  { path: "ops/entities/",               collection: "ops_knowledge",    docType: "Entity",        dept: "ops" },
  { path: "it/concepts/",                collection: "it_knowledge",     docType: "Concept",       dept: "it" },
  { path: "it/decisions/",               collection: "it_knowledge",     docType: "Decision Log",  dept: "it" },
  { path: "it/meeting-notes/",           collection: "it_knowledge",     docType: "Meeting Note",  dept: "it" },
  { path: "it/entities/",               collection: "it_knowledge",     docType: "Entity",        dept: "it" },
];

const COLLECTION_COLORS: Record<string, string> = {
  /* docs collections */
  cac_docs: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  risk_docs: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  legal_docs: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  invest_docs: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  ops_docs: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
  hr_docs: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
  it_docs: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  /* chat collections */
  cac_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  risk_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  legal_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  invest_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  ops_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  hr_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  it_chat: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  /* knowledge collections */
  cac_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  risk_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  legal_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  invest_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  ops_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  hr_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  it_knowledge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  /* shared */
  shared_policies: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

const ACCEPTED_TYPES = ".pdf,.xlsx,.xls,.docx,.txt,.md,.csv";

function getCollectionOptions(dept: string) {
  return [
    { value: `${dept}_docs`, label: `${dept.toUpperCase()} Documents`, desc: "Formal reports, board packs, policy documents" },
    { value: `${dept}_knowledge`, label: `${dept.toUpperCase()} Knowledge`, desc: "Concepts, decision logs, meeting notes (usually via Obsidian)" },
    { value: "shared_policies", label: "Shared Policies", desc: "Cross-department policies, escalation protocols" },
  ];
}

const DOC_CATEGORIES = [
  { value: "", label: "Auto-detect" },
  { value: "report", label: "Report / Analysis" },
  { value: "board_pack", label: "Board Pack / Presentation" },
  { value: "policy", label: "Policy / Procedure" },
  { value: "regulatory", label: "Regulatory Filing" },
  { value: "meeting_minutes", label: "Meeting Minutes" },
  { value: "memo", label: "Internal Memo" },
  { value: "spreadsheet", label: "Spreadsheet / Data Export" },
  { value: "contract", label: "Contract / Agreement" },
  { value: "audit", label: "Audit / Review" },
  { value: "correspondence", label: "Correspondence / Letter" },
];

/* ------------------------------------------------------------------ */
/*  Upload component                                                   */
/* ------------------------------------------------------------------ */

interface UploadResult {
  name: string;
  status: "success" | "error" | "skipped";
  chunks?: number;
  reason?: string;
}

function UploadSection({ dept }: { dept: string }) {
  const collectionOptions = getCollectionOptions(dept);
  const [files, setFiles] = React.useState<File[]>([]);
  const [collection, setCollection] = React.useState(`${dept}_docs`);
  const [category, setCategory] = React.useState("");
  const [tags, setTags] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [uploading, setUploading] = React.useState(false);
  const [results, setResults] = React.useState<UploadResult[]>([]);
  const [dragOver, setDragOver] = React.useState(false);
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  function addFiles(newFiles: FileList | File[]) {
    const arr = Array.from(newFiles);
    setFiles((prev) => [...prev, ...arr]);
    setResults([]);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setResults([]);

    const uploadResults: UploadResult[] = [];

    for (const file of files) {
      try {
        const resp = await apiClient.uploadDocument(file, {
          dept,
          collection,
          category: category || undefined,
          tags: tags || undefined,
          description: description || undefined,
          source: "manual_upload",
        });
        uploadResults.push({
          name: file.name,
          status: resp.status === "ingested" ? "success" : resp.status === "skipped" ? "skipped" : "error",
          chunks: resp.chunks,
          reason: resp.reason,
        });
      } catch {
        uploadResults.push({ name: file.name, status: "error", reason: "Upload failed" });
      }
    }

    setResults(uploadResults);
    setFiles([]);
    setUploading(false);
  }

  function formatSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  const selectedCollection = collectionOptions.find((o) => o.value === collection);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <Upload className="size-5 text-primary" />
        <h2 className="text-lg font-semibold">Upload Documents</h2>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          dragOver
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/30"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <Upload className="mx-auto size-8 text-muted-foreground" />
        <p className="mt-2 text-sm font-medium">
          Drop files here or click to browse
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          PDF, Excel, Word, Text, Markdown, CSV &middot; Max 50 MB per file
        </p>
      </div>

      {/* File list + pipeline config */}
      {files.length > 0 && (
        <div className="space-y-4 rounded-lg border border-border bg-card p-5">
          {/* Files */}
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">
              Files ({files.length})
            </p>
            <div className="rounded-md border border-border divide-y divide-border">
              {files.map((file, i) => (
                <div key={`${file.name}-${i}`} className="flex items-center gap-3 px-3 py-2">
                  <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <p className="text-[10px] text-muted-foreground">{formatSize(file.size)}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Pipeline parameters */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Target collection */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Store in *
              </label>
              <select
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                {collectionOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {selectedCollection && (
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {selectedCollection.desc}
                </p>
              )}
            </div>

            {/* Category */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Document Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                {DOC_CATEGORIES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] text-muted-foreground">
                Helps agents understand what kind of document this is
              </p>
            </div>
          </div>

          {/* Advanced options toggle */}
          <button
            onClick={() => setShowAdvanced((p) => !p)}
            className="text-xs text-primary hover:underline"
          >
            {showAdvanced ? "Hide" : "Show"} advanced options
          </button>

          {showAdvanced && (
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Tags */}
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Tags
                </label>
                <input
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="e.g. q1-2026, board-report, urgent"
                  className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/50"
                />
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Comma-separated tags stored as metadata on each chunk
                </p>
              </div>

              {/* Description */}
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Description
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Q1 2026 ALCO liquidity report from treasury"
                  className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/50"
                />
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Short description for audit trail and agent context
                </p>
              </div>
            </div>
          )}

          {/* Pipeline summary + upload button */}
          <div className="flex items-center justify-between pt-3 border-t border-border">
            <div className="text-xs text-muted-foreground space-y-0.5">
              <p>
                <span className="font-medium">Pipeline:</span>{" "}
                {files.length} file{files.length > 1 ? "s" : ""} → chunk (512 tokens) → embed (Gemini) → {collection}
              </p>
              {category && (
                <p>Category: <span className="text-foreground">{DOC_CATEGORIES.find((c) => c.value === category)?.label}</span></p>
              )}
              {tags && (
                <p>Tags: <span className="text-foreground">{tags}</span></p>
              )}
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className={cn(
                "flex items-center gap-2 rounded-md px-5 py-2.5 text-sm font-medium text-white transition-colors shrink-0",
                uploading
                  ? "bg-primary/60 cursor-not-allowed"
                  : "bg-primary hover:bg-primary/90"
              )}
            >
              {uploading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Upload className="size-4" />
                  Upload &amp; Ingest
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((r, i) => (
            <div
              key={`${r.name}-${i}`}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-4 py-3 text-sm",
                r.status === "success"
                  ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
                  : r.status === "skipped"
                    ? "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30"
                    : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
              )}
            >
              {r.status === "success" ? (
                <CheckCircle2 className="size-4 text-green-600 shrink-0" />
              ) : (
                <XCircle className="size-4 text-red-600 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{r.name}</p>
                {r.status === "success" && r.chunks != null && (
                  <p className="text-xs text-green-700 dark:text-green-400">
                    Ingested — {r.chunks} chunks embedded via Gemini → stored in {collection}
                  </p>
                )}
                {r.reason && (
                  <p className="text-xs text-muted-foreground">{r.reason}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function DataPage() {
  const { dept } = useParams<{ dept: string }>();
  const department = getDepartment(dept);
  const dataAccess = department?.dataAccess;

  const collections = dataAccess?.qdrantCollections ?? [];
  const mirrorPaths = dataAccess?.mirrorPaths ?? [];
  const excelFiles = dataAccess?.excelFiles ?? [];

  const relevantVaultFolders = VAULT_FOLDERS.filter(
    (f) => f.dept === dept || f.dept === "shared"
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Data Sources</h1>
        <p className="text-muted-foreground">
          Knowledge base, collections, and data mirrors for{" "}
          {department?.name ?? dept}
        </p>
      </div>

      {/* Data Flow Guide */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Where does data go?</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">

          {/* Qdrant — docs */}
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Database className="size-5 text-blue-600" />
              <h3 className="text-sm font-semibold">Qdrant — {dept}_docs</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Formal documents uploaded via this page or Slack. Chunked, embedded, and searchable by agents.
            </p>
            <div className="pt-2 border-t border-blue-200/50 dark:border-blue-800/50 space-y-1">
              <p className="text-[10px] font-medium text-blue-700 dark:text-blue-400">What to put here:</p>
              <div className="flex flex-wrap gap-1">
                {["PDF reports", "Board packs", "Policy docs", "Excel exports", "Word memos"].map((t) => (
                  <span key={t} className="rounded bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[10px] text-blue-700 dark:text-blue-400">{t}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Upload className="size-3" />
              <span>Upload here</span>
              <ArrowRight className="size-3" />
              <span>rag-ingestion</span>
              <ArrowRight className="size-3" />
              <span>chunk + embed</span>
              <ArrowRight className="size-3" />
              <Database className="size-3" />
            </div>
          </div>

          {/* Qdrant — chat */}
          <div className="rounded-lg border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <MessageSquare className="size-5 text-purple-600" />
              <h3 className="text-sm font-semibold">Qdrant — {dept}_chat</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Slack messages auto-indexed by the Slack bot. Every message in the committee channel is embedded for agent retrieval.
            </p>
            <div className="pt-2 border-t border-purple-200/50 dark:border-purple-800/50 space-y-1">
              <p className="text-[10px] font-medium text-purple-700 dark:text-purple-400">Auto-ingested from:</p>
              <div className="flex flex-wrap gap-1">
                {["Slack messages", "Thread replies", "File shares", "Committee discussions"].map((t) => (
                  <span key={t} className="rounded bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-[10px] text-purple-700 dark:text-purple-400">{t}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <MessageSquare className="size-3" />
              <span>Slack message</span>
              <ArrowRight className="size-3" />
              <span>slack-bot</span>
              <ArrowRight className="size-3" />
              <span>auto-embed</span>
              <ArrowRight className="size-3" />
              <Database className="size-3" />
            </div>
          </div>

          {/* Qdrant — knowledge */}
          <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <BookOpen className="size-5 text-emerald-600" />
              <h3 className="text-sm font-semibold">Qdrant — {dept}_knowledge</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Obsidian vault articles auto-ingested by the vault watcher. Human-authored knowledge: concepts, decisions, meeting notes.
            </p>
            <div className="pt-2 border-t border-emerald-200/50 dark:border-emerald-800/50 space-y-1">
              <p className="text-[10px] font-medium text-emerald-700 dark:text-emerald-400">Auto-ingested from Obsidian:</p>
              <div className="flex flex-wrap gap-1">
                {["Concept notes", "Decision logs", "Meeting notes", "Entity profiles", "Trend analysis"].map((t) => (
                  <span key={t} className="rounded bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:text-emerald-400">{t}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Pencil className="size-3" />
              <span>Edit in Obsidian</span>
              <ArrowRight className="size-3" />
              <span>vault watcher</span>
              <ArrowRight className="size-3" />
              <span>auto-embed</span>
              <ArrowRight className="size-3" />
              <Database className="size-3" />
            </div>
          </div>

          {/* Data Mirror */}
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <HardDrive className="size-5 text-gray-600" />
              <h3 className="text-sm font-semibold">Data Mirror (Read-Only)</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Corporate source of truth synced every 15 min via SMB/SharePoint/SFTP. Agents read from here but can NEVER write to it.
            </p>
            <div className="pt-2 border-t border-gray-200/50 dark:border-gray-700/50 space-y-1">
              <p className="text-[10px] font-medium text-gray-600 dark:text-gray-400">Contains:</p>
              <div className="flex flex-wrap gap-1">
                {["Live Excel trackers", "Corporate reports", "Regulatory filings", "Audit docs"].map((t) => (
                  <span key={t} className="rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-600 dark:text-gray-400">{t}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <Globe className="size-3" />
              <span>Corporate system</span>
              <ArrowRight className="size-3" />
              <span>sync-mirror</span>
              <ArrowRight className="size-3" />
              <span>/data/mirror/</span>
              <ArrowRight className="size-3" />
              <ShieldCheck className="size-3" />
              <span>read-only</span>
            </div>
          </div>

          {/* Excel Trackers */}
          <div className="rounded-lg border border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="size-5 text-green-600" />
              <h3 className="text-sm font-semibold">Excel Trackers</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Agents propose cell changes to these files. Changes go to staging, NOT the live file. HOD approves before sync-back writes.
            </p>
            <div className="pt-2 border-t border-green-200/50 dark:border-green-800/50 space-y-1">
              <p className="text-[10px] font-medium text-green-700 dark:text-green-400">Flow:</p>
              <div className="flex flex-wrap gap-1">
                {excelFiles.map((f) => (
                  <span key={f} className="rounded bg-green-100 dark:bg-green-900/40 px-1.5 py-0.5 text-[10px] text-green-700 dark:text-green-400">{f}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span>Agent proposes</span>
              <ArrowRight className="size-3" />
              <span>/data/staging/</span>
              <ArrowRight className="size-3" />
              <span>HOD approves</span>
              <ArrowRight className="size-3" />
              <span>sync-back writes</span>
            </div>
          </div>

          {/* Staging Pipeline */}
          <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-amber-600" />
              <h3 className="text-sm font-semibold">Staging Pipeline</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              All agent-proposed changes land here first. Nothing touches corporate data without human approval.
            </p>
            <div className="pt-2 border-t border-amber-200/50 dark:border-amber-800/50 space-y-1">
              <p className="text-[10px] font-medium text-amber-700 dark:text-amber-400">Sub-folders:</p>
              <div className="flex flex-wrap gap-1">
                {["pending/ (awaiting review)", "approved/ (HOD accepted)", "rejected/ (HOD denied)"].map((t) => (
                  <span key={t} className="rounded bg-amber-100 dark:bg-amber-900/40 px-1.5 py-0.5 text-[10px] text-amber-700 dark:text-amber-400">{t}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span>Agent writes</span>
              <ArrowRight className="size-3" />
              <span>pending/</span>
              <ArrowRight className="size-3" />
              <span>email to HOD</span>
              <ArrowRight className="size-3" />
              <span>approve/reject</span>
            </div>
          </div>

        </div>
      </section>

      {/* Upload */}
      <UploadSection dept={dept} />

      {/* Qdrant Collections */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Database className="size-5 text-primary" />
          <h2 className="text-lg font-semibold">Vector Collections (Qdrant)</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {collections.map((col) => (
            <div
              key={col}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
            >
              <div
                className={`flex size-9 items-center justify-center rounded-md text-xs font-bold ${COLLECTION_COLORS[col] ?? "bg-gray-100 text-gray-600"}`}
              >
                <Database className="size-4" />
              </div>
              <div>
                <p className="text-sm font-medium">{col}</p>
                <p className="text-xs text-muted-foreground">
                  {col.includes("docs")
                    ? "Documents & reports"
                    : col.includes("chat")
                      ? "Slack conversations"
                      : col.includes("knowledge")
                        ? "Obsidian vault"
                        : "Shared policies"}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Obsidian Vault */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <BookOpen className="size-5 text-primary" />
          <h2 className="text-lg font-semibold">Obsidian Vault</h2>
        </div>
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2.5 text-left font-medium">Folder</th>
                <th className="px-4 py-2.5 text-left font-medium">Doc Type</th>
                <th className="px-4 py-2.5 text-left font-medium">Collection</th>
              </tr>
            </thead>
            <tbody>
              {relevantVaultFolders.map((f) => (
                <tr key={f.path} className="border-b border-border last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <FolderOpen className="size-4 text-muted-foreground" />
                      <code className="text-xs">{f.path}</code>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{f.docType}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${COLLECTION_COLORS[f.collection] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {f.collection}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Mirror Paths */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <HardDrive className="size-5 text-primary" />
          <h2 className="text-lg font-semibold">Data Mirror (Read-Only)</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {mirrorPaths.map((p) => (
            <div
              key={p}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
            >
              <FolderOpen className="size-5 text-muted-foreground" />
              <div>
                <code className="text-sm">{p}</code>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Synced every 15 minutes from corporate source
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Excel Files */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Table2 className="size-5 text-primary" />
          <h2 className="text-lg font-semibold">Excel Trackers</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {excelFiles.map((f) => (
            <div
              key={f}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
            >
              <FileText className="size-5 text-green-600" />
              <div>
                <p className="text-sm font-medium">{f}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Agent proposals target cells in this file
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Sensitivity Level */}
      {dataAccess?.sensitivityLevel && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 p-4">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
            Data Sensitivity: <span className="capitalize">{dataAccess.sensitivityLevel}</span>
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
            All data access is logged. Agents can only write to staging — never directly to corporate data.
          </p>
        </div>
      )}
    </div>
  );
}
