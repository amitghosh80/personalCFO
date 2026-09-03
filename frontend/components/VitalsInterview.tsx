"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getFinancialVitals, saveFinancialVitals } from "@/lib/api";
import { track } from "@/lib/track";
import type { VitalsInput } from "@/lib/types";

type FieldKey = keyof VitalsInput;

interface StepConfig {
  key: FieldKey;
  question: string;
  helper: string;
  allowZero: boolean;
  showRunningTotal?: boolean;
}

const SPEND_FIELDS: FieldKey[] = ["food_monthly", "transportation_monthly", "other_monthly"];

const STEPS: StepConfig[] = [
  {
    key: "take_home_pay_monthly",
    question: "What is your monthly take-home pay?",
    helper: "The amount that actually lands in your bank account each month, after taxes and deductions.",
    allowZero: false,
  },
  {
    key: "rent_or_mortgage_monthly",
    question: "How much do you pay for rent or mortgage each month?",
    helper: "Your regular housing payment.",
    allowZero: true,
  },
  {
    key: "car_payment_monthly",
    question: "How much is your car payment each month?",
    helper: "Your regular auto loan or lease payment.",
    allowZero: true,
  },
  {
    key: "food_monthly",
    question: "About how much do you spend on food each month?",
    helper: "Groceries, takeout, and dining out combined.",
    allowZero: true,
    showRunningTotal: true,
  },
  {
    key: "transportation_monthly",
    question: "About how much do you spend on transportation each month?",
    helper: "Gas, transit, rideshare, and parking — not your car payment, that's already counted.",
    allowZero: true,
    showRunningTotal: true,
  },
  {
    key: "other_monthly",
    question: "About how much do you spend on everything else each month?",
    helper: "Shopping, subscriptions, entertainment, and anything not already covered.",
    allowZero: true,
    showRunningTotal: true,
  },
];

const MAX_AMOUNT = 1_000_000;
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

function validateAmount(raw: string, allowZero: boolean): string | null {
  const trimmed = raw.trim();
  if (trimmed === "" || !AMOUNT_PATTERN.test(trimmed)) {
    return "Enter a valid amount with up to two decimal places.";
  }
  const value = Number(trimmed);
  if (value > MAX_AMOUNT) return "Amount must be $1,000,000 or less.";
  if (!allowZero && value <= 0) return "This must be greater than zero.";
  return null;
}

const EMPTY_VALUES: Record<FieldKey, string> = {
  take_home_pay_monthly: "",
  rent_or_mortgage_monthly: "",
  car_payment_monthly: "",
  food_monthly: "",
  transportation_monthly: "",
  other_monthly: "",
};

function money(n: number) {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function VitalsInterview() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [values, setValues] = useState<Record<FieldKey, string>>(EMPTY_VALUES);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    track("vitals_started");
    getFinancialVitals()
      .then((vitals) => {
        if (!vitals) return;
        setValues({
          take_home_pay_monthly: String(vitals.take_home_pay_monthly),
          rent_or_mortgage_monthly: String(vitals.rent_or_mortgage_monthly),
          car_payment_monthly: String(vitals.car_payment_monthly),
          food_monthly: String(vitals.food_monthly),
          transportation_monthly: String(vitals.transportation_monthly),
          other_monthly: String(vitals.other_monthly),
        });
      })
      .catch(() => {
        // Editing an existing estimate is a nice-to-have prefill — a failed
        // fetch just means the user starts from blank fields.
      });
  }, []);

  const current = STEPS[step];
  const isLastStep = step === STEPS.length - 1;

  function setValue(v: string) {
    setValues((prev) => ({ ...prev, [current.key]: v }));
    setError(null);
  }

  function runningSpendTotal(upToKey: FieldKey, values: Record<FieldKey, string>): number {
    let total = 0;
    for (const key of SPEND_FIELDS) {
      const n = Number(values[key]);
      if (Number.isFinite(n)) total += n;
      if (key === upToKey) break;
    }
    return total;
  }

  async function submit(finalValues: Record<FieldKey, string>) {
    setSaving(true);
    setSubmitError(null);
    try {
      await saveFinancialVitals({
        take_home_pay_monthly: Number(finalValues.take_home_pay_monthly),
        rent_or_mortgage_monthly: Number(finalValues.rent_or_mortgage_monthly),
        car_payment_monthly: Number(finalValues.car_payment_monthly),
        food_monthly: Number(finalValues.food_monthly),
        transportation_monthly: Number(finalValues.transportation_monthly),
        other_monthly: Number(finalValues.other_monthly),
      });
      track("vitals_completed");
      router.push("/profile");
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Something went wrong saving your answers. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleContinue() {
    const err = validateAmount(values[current.key], current.allowZero);
    if (err) {
      setError(err);
      track("vitals_validation_error", { field: current.key });
      return;
    }

    if (isLastStep) {
      const combinedSpend = SPEND_FIELDS.reduce((sum, key) => sum + Number(values[key] || 0), 0);
      if (combinedSpend <= 0) {
        setError("Your food, transportation, and other spending can't all be zero.");
        track("vitals_validation_error", { field: "combined_spend" });
        return;
      }
      submit(values);
    } else {
      setStep((s) => s + 1);
    }
  }

  function handleBack() {
    setError(null);
    setSubmitError(null);
    setStep((s) => Math.max(0, s - 1));
  }

  return (
    <div className="max-w-md mx-auto">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
        {step + 1} of {STEPS.length}
      </p>
      <h2 className="text-xl font-bold text-gray-900">{current.question}</h2>
      <p className="mt-1 text-sm text-gray-500">{current.helper}</p>

      <div className="mt-6">
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
          <input
            type="text"
            inputMode="decimal"
            value={values[current.key]}
            onChange={(e) => setValue(e.target.value)}
            className="w-full rounded-lg border border-gray-300 pl-7 pr-3 py-2.5 text-lg focus:border-blue-400 focus:outline-none"
            placeholder="0.00"
            autoFocus
          />
        </div>
        {current.allowZero && (
          <button type="button" onClick={() => setValue("0")} className="mt-2 text-xs text-blue-600 hover:underline">
            I do not have this
          </button>
        )}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        {current.showRunningTotal && (
          <p className="mt-2 text-xs text-gray-400">
            Spending so far: {money(runningSpendTotal(current.key, values))}/mo
          </p>
        )}
      </div>

      {submitError && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {submitError}
        </div>
      )}

      <p className="mt-6 text-xs text-gray-400">
        This is an estimate, not verified financial data — you can update it any time.
      </p>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={handleBack}
          disabled={step === 0 || saving}
          className="text-sm font-medium text-gray-500 hover:text-gray-800 disabled:opacity-40"
        >
          Back
        </button>
        <button
          type="button"
          onClick={handleContinue}
          disabled={saving}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {saving ? "Saving…" : isLastStep ? "See my estimated profile" : "Continue"}
        </button>
      </div>
    </div>
  );
}
