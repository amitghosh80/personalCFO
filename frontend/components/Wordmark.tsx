export default function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-bold tracking-tight text-gray-900 ${className}`}>
      <img src="/logo-icon.png" alt="" className="h-7 w-7 rounded-md" />
      <span>personal<span className="text-blue-600">CFO</span></span>
    </span>
  );
}
