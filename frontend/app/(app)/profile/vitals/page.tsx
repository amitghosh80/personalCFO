import VitalsInterview from "@/components/VitalsInterview";

export default function VitalsInterviewPage() {
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Financial Vitals</h2>
        <p className="text-gray-500 mt-1">Four quick questions to estimate your Financial Profile.</p>
      </div>
      <VitalsInterview />
    </div>
  );
}
