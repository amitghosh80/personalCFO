export default function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-bold tracking-tight ${className}`}>
      personal<span className="text-blue-600">CFO</span>
    </span>
  );
}
