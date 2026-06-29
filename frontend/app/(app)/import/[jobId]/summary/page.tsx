import ImportSummary from "@/components/ImportSummary";

export default function SummaryPage({ params }: { params: { jobId: string } }) {
  return <ImportSummary jobId={params.jobId} />;
}
