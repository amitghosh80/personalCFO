import TransactionTable from "@/components/TransactionTable";

export default function TransactionsPage({
  searchParams,
}: {
  searchParams: { job?: string };
}) {
  return <TransactionTable jobId={searchParams.job} />;
}
