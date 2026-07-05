"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { uploadStatements } from "@/lib/api";

const MAX_FILES = 10;

type FileStatus = "ready" | "uploading" | "done" | "error";

interface FileEntry {
  file: File;
  id: string;
  status: FileStatus;
  message?: string;
}

const rid = () => Math.random().toString(36).slice(2);

export default function FileUploader() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set when every file was a duplicate: the existing import to view instead.
  const [existingJobId, setExistingJobId] = useState<string | null>(null);
  const router = useRouter();

  const onDrop = useCallback((accepted: File[]) => {
    setError(null);
    setExistingJobId(null);
    setFiles((prev) => {
      // Cap counts only files that are still candidates for upload.
      const current = prev.filter((f) => f.status !== "error").length;
      const slots = Math.max(0, MAX_FILES - current);
      if (accepted.length > slots) {
        queueMicrotask(() =>
          setError(`You can upload up to ${MAX_FILES} files at once — extra files were not added.`)
        );
      }
      const add: FileEntry[] = accepted.slice(0, slots).map((f) => ({
        file: f,
        id: rid(),
        status: "ready",
      }));
      return [...prev, ...add];
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"], "application/pdf": [".pdf"] },
    maxSize: 20 * 1024 * 1024,
    disabled: uploading,
    // Rejected files (wrong type / too large) are shown inline as error rows,
    // rather than as one global message, so each file's problem is clear.
    onDropRejected: (rejected) => {
      const errs: FileEntry[] = rejected.map((r) => ({
        file: r.file,
        id: rid(),
        status: "error",
        message: r.errors
          .map((e) =>
            e.code === "file-too-large"
              ? "exceeds 20MB — export a shorter date range"
              : e.code === "file-invalid-type"
              ? "unsupported type — only PDF and CSV"
              : e.message
          )
          .join(", "),
      }));
      setFiles((prev) => [...prev, ...errs]);
    },
  });

  const removeFile = (id: string) =>
    setFiles((prev) => prev.filter((f) => f.id !== id));

  const uploadable = files.filter((f) => f.status === "ready");

  const handleUpload = async () => {
    if (!uploadable.length) return;
    setUploading(true);
    setError(null);
    setFiles((prev) =>
      prev.map((f) => (f.status === "ready" ? { ...f, status: "uploading" } : f))
    );
    try {
      const result = await uploadStatements(uploadable.map((f) => f.file));
      const byName = new Map(result.file_results.map((r) => [r.file, r]));
      setFiles((prev) =>
        prev.map((f) => {
          if (f.status !== "uploading") return f;
          const r = byName.get(f.file.name);
          if (r?.error) return { ...f, status: "error", message: r.error };
          const saved = r?.transactions_saved ?? 0;
          const inst = r?.institution ? `${r.institution} · ` : "";
          return { ...f, status: "done", message: `${inst}${saved} transactions` };
        })
      );
      try {
        sessionStorage.setItem(`upload:${result.import_job_id}`, JSON.stringify(result));
      } catch {
        /* sessionStorage unavailable — scan still works, just no per-file summary */
      }
      if (result.total_transactions > 0) {
        router.push(`/import/${result.import_job_id}/scan`);
      } else {
        // Everything was a duplicate. Don't dead-end — point to the existing
        // import's summary (category + month-wise totals) if we know it.
        setUploading(false);
        const existing =
          result.existing_job_id ??
          result.file_results.find((r) => r.existing_job_id)?.existing_job_id ??
          null;
        if (existing) {
          setExistingJobId(existing);
        } else {
          setError("No new transactions were imported — these files may already have been imported.");
        }
      }
    } catch (e) {
      setFiles((prev) =>
        prev.map((f) =>
          f.status === "uploading" ? { ...f, status: "error", message: "upload failed" } : f
        )
      );
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  const atCap = uploadable.length >= MAX_FILES;

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors select-none ${
          uploading || atCap ? "cursor-not-allowed opacity-60" : "cursor-pointer"
        } ${
          isDragActive
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50"
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-3">📄</div>
        <p className="text-gray-700 font-medium">
          {isDragActive ? "Drop your files here" : "Drag & drop statements here"}
        </p>
        <p className="text-sm text-gray-400 mt-1">
          CSV or PDF · up to 20 MB each · up to {MAX_FILES} files
        </p>
        <button
          type="button"
          disabled={uploading || atCap}
          className="mt-4 px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-gray-700 disabled:opacity-50"
        >
          Browse files
        </button>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map(({ file, id, status, message }) => (
            <li
              key={id}
              className={`flex items-center justify-between border rounded-lg px-4 py-3 ${
                status === "error"
                  ? "bg-red-50 border-red-200"
                  : status === "done"
                  ? "bg-green-50 border-green-200"
                  : "bg-white border-gray-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-lg shrink-0">
                  {status === "uploading" ? (
                    <span className="inline-block h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  ) : status === "done" ? (
                    "✅"
                  ) : status === "error" ? (
                    "⚠️"
                  ) : file.name.endsWith(".pdf") ? (
                    "📕"
                  ) : (
                    "📊"
                  )}
                </span>
                <span className="text-sm font-medium text-gray-800 truncate">{file.name}</span>
                <span
                  className={`text-xs shrink-0 ${
                    status === "error" ? "text-red-600" : "text-gray-400"
                  }`}
                >
                  {status === "uploading"
                    ? "Uploading…"
                    : message
                    ? message
                    : `${(file.size / 1024).toFixed(0)} KB`}
                </span>
              </div>
              {status !== "uploading" && (
                <button
                  onClick={() => removeFile(id)}
                  className="text-gray-300 hover:text-red-500 transition-colors ml-4 text-lg leading-none"
                  aria-label="Remove file"
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {existingJobId && (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <p className="text-sm text-blue-800">
            These statements were already imported. View their spending categories and
            month-by-month totals.
          </p>
          <button
            onClick={() => router.push(`/import/${existingJobId}/summary`)}
            className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          >
            View import →
          </button>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!uploadable.length || uploading}
        className="w-full py-3 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {uploading
          ? "Processing statements…"
          : uploadable.length
          ? `Upload ${uploadable.length} file${uploadable.length > 1 ? "s" : ""}`
          : "Select files to upload"}
      </button>
    </div>
  );
}
