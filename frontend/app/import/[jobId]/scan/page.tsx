import ScanAnimation from "@/components/ScanAnimation";

export default function ScanPage({ params }: { params: { jobId: string } }) {
  return <ScanAnimation jobId={params.jobId} />;
}
