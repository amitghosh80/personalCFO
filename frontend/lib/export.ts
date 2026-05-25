import type { Transaction } from "./types";

const CATEGORY_LABELS: Record<string, string> = {
  salary: "Salary / Payroll",
  interest: "Interest / Dividend",
  rental: "Rental Income",
  gig: "Gig / Freelance",
  other: "Other Income",
};

function toRows(transactions: Transaction[], categoryOverrides: Record<number, string>) {
  return transactions.map((t) => ({
    Date: t.date,
    Description: t.description,
    "Amount (USD)": t.amount,
    Category: CATEGORY_LABELS[categoryOverrides[t.id] ?? t.income_category ?? ""] ?? "",
    Institution: t.institution ?? "",
    "Account (last 4)": t.account_last4 ?? "",
  }));
}

export async function exportToExcel(
  sections: { name: string; transactions: Transaction[]; categoryOverrides: Record<number, string> }[],
  filename: string
) {
  const { utils, writeFile } = await import("xlsx");
  const wb = utils.book_new();
  for (const { name, transactions, categoryOverrides } of sections) {
    const ws = utils.json_to_sheet(toRows(transactions, categoryOverrides));
    // Column widths
    ws["!cols"] = [
      { wch: 12 }, // Date
      { wch: 50 }, // Description
      { wch: 14 }, // Amount
      { wch: 22 }, // Category
      { wch: 20 }, // Institution
      { wch: 16 }, // Account
    ];
    utils.book_append_sheet(wb, ws, name.slice(0, 31)); // sheet name max 31 chars
  }
  writeFile(wb, filename);
}
