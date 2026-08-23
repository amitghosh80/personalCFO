"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChatToolUse } from "@/lib/types";
import {
  CHART_AQUA,
  CHART_AXIS,
  CHART_BLUE,
  CHART_BLUE_DARK,
  CHART_BLUE_LIGHT,
  CHART_GRID,
  CHART_INK_MUTED,
  CHART_INK_SECONDARY,
  CHART_RED,
  formatUsd,
  humanizeKey,
  monthLabel,
} from "@/lib/chartPalette";

const MAX_ROWS = 7;

interface Row {
  display: string;
  amount: number;
}

function foldTail(rows: Row[]): Row[] {
  const top = rows.slice(0, MAX_ROWS);
  const restAmount = rows.slice(MAX_ROWS).reduce((s, r) => s + r.amount, 0);
  return restAmount > 0.005 ? [...top, { display: "Other", amount: restAmount }] : top;
}

function ChartCard({ title, children, height }: { title: string; children: React.ReactNode; height: number }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 mt-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-2">{title}</p>
      <ResponsiveContainer width="100%" height={height}>
        {children as never}
      </ResponsiveContainer>
    </div>
  );
}

function CategoryBarChart({ rows, hue, title }: { rows: Row[]; hue: string; title: string }) {
  const data = foldTail(rows);
  if (data.length === 0) return null;
  const height = Math.max(90, data.length * 32 + 20);

  return (
    <ChartCard title={title} height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 44, left: 4, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke={CHART_GRID} />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="display"
          width={112}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_INK_SECONDARY, fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "rgba(11,11,11,0.04)" }}
          formatter={(v) => formatUsd(Number(v))}
          contentStyle={{ borderRadius: 8, border: `1px solid ${CHART_GRID}`, fontSize: 12 }}
        />
        <Bar dataKey="amount" fill={hue} radius={[0, 4, 4, 0]} maxBarSize={20}>
          {data.map((_, i) => (
            <Cell key={i} />
          ))}
        </Bar>
      </BarChart>
    </ChartCard>
  );
}

function CashflowChart({
  months,
  label,
}: {
  months: { month: string; credits: number; debits: number }[];
  label?: string;
}) {
  const data = months.map((m) => ({ ...m, label: monthLabel(m.month) }));
  return (
    <ChartCard title={`Money in vs. out${label ? ` — ${label}` : ""}`} height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 4, bottom: 0 }} barGap={2}>
        <CartesianGrid vertical={false} stroke={CHART_GRID} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={{ stroke: CHART_AXIS }}
          tick={{ fill: CHART_INK_MUTED, fontSize: 11 }}
        />
        <YAxis hide />
        <Tooltip
          cursor={{ fill: "rgba(11,11,11,0.04)" }}
          formatter={(v) => formatUsd(Number(v))}
          contentStyle={{ borderRadius: 8, border: `1px solid ${CHART_GRID}`, fontSize: 12 }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: CHART_INK_SECONDARY }}
          iconType="circle"
          iconSize={8}
        />
        <Bar dataKey="credits" name="Money in" fill={CHART_BLUE} radius={[4, 4, 0, 0]} maxBarSize={22} />
        <Bar dataKey="debits" name="Money out" fill={CHART_RED} radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </ChartCard>
  );
}

function ComparePeriodsChart({
  periodA,
  periodB,
  category,
}: {
  periodA: { label: string; total: number };
  periodB: { label: string; total: number };
  category?: string;
}) {
  const data = [
    { label: periodA.label, amount: periodA.total, fill: CHART_BLUE_LIGHT },
    { label: periodB.label, amount: periodB.total, fill: CHART_BLUE_DARK },
  ];
  const title = category && category !== "all" ? `${humanizeKey(category)} — period comparison` : "Period comparison";
  return (
    <ChartCard title={title} height={140}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 44, left: 4, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke={CHART_GRID} />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={112}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_INK_SECONDARY, fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: "rgba(11,11,11,0.04)" }}
          formatter={(v) => formatUsd(Number(v))}
          contentStyle={{ borderRadius: 8, border: `1px solid ${CHART_GRID}`, fontSize: 12 }}
        />
        <Bar dataKey="amount" radius={[0, 4, 4, 0]} maxBarSize={22}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.fill} />
          ))}
        </Bar>
      </BarChart>
    </ChartCard>
  );
}

/** Renders a chart for a tool call result, when the tool's data supports one.
 * Returns null for tools with no visualizable shape (e.g. search_transactions). */
export default function ChatToolChart({ tool }: { tool: ChatToolUse }) {
  const r = tool.result as Record<string, any> | undefined;
  if (!r) return null;

  try {
    switch (tool.name) {
      case "spending_by_category": {
        const rows: Row[] = (r.by_primary ?? []).map((x: any) => ({ display: x.display, amount: x.amount }));
        if (rows.length === 0) return null;
        return <CategoryBarChart rows={rows} hue={CHART_BLUE} title={`Spending by category — ${r.period?.label ?? "all time"}`} />;
      }
      case "income_summary": {
        const rows: Row[] = (r.by_category ?? []).map((x: any) => ({ display: humanizeKey(x.category), amount: x.amount }));
        if (rows.length === 0) return null;
        return <CategoryBarChart rows={rows} hue={CHART_AQUA} title={`Income by category — ${r.period?.label ?? "all time"}`} />;
      }
      case "cashflow_summary": {
        const months = r.by_month ?? [];
        if (months.length === 0) return null;
        return <CashflowChart months={months} label={r.period?.label} />;
      }
      case "compare_periods": {
        if (!r.period_a || !r.period_b) return null;
        return <ComparePeriodsChart periodA={r.period_a} periodB={r.period_b} category={r.category} />;
      }
      case "recurring_charges": {
        const rows: Row[] = (r.recurring ?? [])
          .slice(0, MAX_ROWS)
          .map((x: any) => ({ display: `${x.merchant} (${x.display})`, amount: x.typical_amount }));
        if (rows.length === 0) return null;
        return <CategoryBarChart rows={rows} hue={CHART_BLUE} title="Recurring charges" />;
      }
      default:
        return null;
    }
  } catch {
    return null;
  }
}

