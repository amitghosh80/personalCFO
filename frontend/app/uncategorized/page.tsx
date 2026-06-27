import UncategorizedQueue from "@/components/UncategorizedQueue";

export default function UncategorizedPage({
  searchParams,
}: {
  searchParams: { job?: string };
}) {
  return <UncategorizedQueue jobId={searchParams.job} />;
}
