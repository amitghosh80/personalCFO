"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { uploadStatements } from "@/lib/api";

interface FileEntry {
  file: File;
  id: string;
}

export default function FileUploader() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const onDrop = useCallback((accepted: File[]) => {
    const entries: FileEntry[] = accepted.map((f) => ({
      file: f,
      id: Math.random().toString(36).slice(2),
    }));
    setFiles((prev) => [...prev, ...entries]);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"], "application/pdf": [".pdf"] },
    maxSize: 20 * 1024 * 1024,
    onDropRejected: (rejected) => {
      const reasons = rejected
        .map((r) => `${r.file.name}: ${r.errors.map((e) =>
          e.code === "file-too-large"
            ? "exceeds 20MB — try exporting a shorter date range"
            : e.code === "file-invalid-type"
            ? "only PDF and CSV files are supported"
            : e.message
        ).join(", ")}`)
        .join("; ");
      setError(reasons);
    },
  });

  const removeFile = (id: string) =>
    setFiles((prev) => prev.filter((f) => f.id !== id));

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadStatements(files.map((f) => f.file));
      // Stash the per-file results so the scan's completion screen can show them.
      try {
        sessionStorage.setItem(`upload:${result.import_job_id}`, JSON.stringify(result));
      } catch {
        /* sessionStorage unavailable — scan still works, just no per-file summary */
      }
      router.push(`/import/${result.import_job_id}/scan`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors select-none ${
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
        <p className="text-sm text-gray-400 mt-1">CSV or PDF · up to 20 MB each · multiple files supported</p>
        <button
          type="button"
          className="mt-4 px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-gray-700"
        >
          Browse files
        </button>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map(({ file, id }) => (
            <li
              key={id}
              className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-gray-400 text-lg">{file.name.endsWith(".pdf") ? "📕" : "📊"}</span>
                <span className="text-sm font-medium text-gray-800 truncate">{file.name}</span>
                <span className="text-xs text-gray-400 shrink-0">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
              </div>
              <button
                onClick={() => removeFile(id)}
                className="text-gray-300 hover:text-red-500 transition-colors ml-4 text-lg leading-none"
                aria-label="Remove file"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      <button
        onClick={handleUpload}
        disabled={!files.length || uploading}
        className="w-full py-3 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {uploading
          ? "Processing statements…"
          : files.length
          ? `Upload ${files.length} file${files.length > 1 ? "s" : ""}`
          : "Select files to upload"}
      </button>
    </div>
  );
}
