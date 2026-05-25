import FileUploader from "@/components/FileUploader";

export default function HomePage() {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Import Statements</h2>
        <p className="text-gray-500 mt-1">
          Upload your bank or credit card statements. We support CSV exports and PDF statements
          from Chase, Bank of America, Citi, Capital One, American Express, and Wells Fargo.
        </p>
      </div>
      <FileUploader />
    </div>
  );
}
