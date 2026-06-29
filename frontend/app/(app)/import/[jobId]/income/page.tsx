import IncomeReview from "@/components/IncomeReview";

export default function IncomePage({ params }: { params: { jobId: string } }) {
  return <IncomeReview jobId={params.jobId} />;
}
