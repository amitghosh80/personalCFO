import TransactionTable from "@/components/TransactionTable";

export default function TransactionsPage({
  searchParams,
}: {
  searchParams: { job?: string; category?: string; month?: string; type?: string };
}) {
  const type =
    searchParams.type === "debit" || searchParams.type === "credit"
      ? searchParams.type
      : undefined;
  return (
    <TransactionTable
      jobId={searchParams.job}
      initialCategory={searchParams.category}
      initialMonth={searchParams.month}
      initialType={type}
    />
  );
}
