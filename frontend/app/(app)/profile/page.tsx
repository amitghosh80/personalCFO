import FinancialProfile from "@/components/FinancialProfile";

export default function ProfilePage() {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Financial Profile</h2>
        <p className="text-gray-500 mt-1">
          Your standing financial metrics — estimated until you import a statement, then computed from your ledger.
        </p>
      </div>
      <FinancialProfile />
    </div>
  );
}
