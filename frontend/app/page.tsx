"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";

type PercentileSeries = {
  p10_cents: number[];
  p50_cents: number[];
  p90_cents: number[];
};

type SimulationResult = {
  decision_id: string;
  horizon_months: number;
  baseline_final_net_worth_cents: number;
  scenario_final_net_worth_cents: number;
  delta_final_net_worth_cents: number;
  downside_p10_delta_cents: number;
  confidence: number;
  goal_success_probability: number;
  scenario_beats_baseline_probability: number;
  baseline_timeline: PercentileSeries;
  timeline: PercentileSeries;
};

type Recommendation = {
  recommendation_id: string;
  title: string;
  action_type: string;
  score: number;
  confidence: number;
  goal_success_probability: number;
  expected_net_worth_delta: { amount_cents: number; currency: "CAD" };
  downside_p10_delta: { amount_cents: number; currency: "CAD" };
  rationale: string[];
  risk_level: "low" | "moderate" | "high";
};

type ExecutionPreview = {
  preview_id: string;
  action_id: string;
  requires_confirmation: true;
  projected_impact_12m: { amount_cents: number; currency: "CAD" };
  fees: { amount_cents: number; currency: "CAD" };
  warnings: string[];
  expires_at: string;
};

type ExecutionResult = {
  execution_id: string;
  status: string;
  executed_at: string;
  upstream_reference: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function cad(cents: number) {
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(
    cents / 100
  );
}

function confidenceBand(confidence: number): string {
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

function MetricWithHelp({ label, value, help }: { label: string; value: string | ReactNode; help: string }) {
  return (
    <div className="metric-row">
      <p>
        <span className="metric-label">{label}:</span> {value}
      </p>
      <span className="metric-hint" tabIndex={0} aria-label={`${label} details`}>
        i
        <span className="metric-tooltip" role="tooltip">
          {help}
        </span>
      </span>
    </div>
  );
}

function projectionVerdict(simulation: SimulationResult): string {
  if (simulation.delta_final_net_worth_cents > 0) {
    return "Your scenario currently projects a better financial outcome than staying on your current path.";
  }
  if (simulation.delta_final_net_worth_cents < 0) {
    return "Your scenario currently projects a weaker financial outcome than your current path.";
  }
  return "Your scenario and current path are currently projecting similar outcomes.";
}

function linePath(values: number[], width: number, height: number, minValue: number, maxValue: number): string {
  if (values.length === 0) return "";
  const range = Math.max(1, maxValue - minValue);
  return values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * width;
      const y = height - ((value - minValue) / range) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function FutureChart({ baseline, scenario }: { baseline: number[]; scenario: number[] }) {
  const width = 560;
  const height = 160;
  const combined = [...baseline, ...scenario];
  const minValue = Math.min(...combined);
  const maxValue = Math.max(...combined);
  const baselinePath = linePath(baseline, width, height, minValue, maxValue);
  const scenarioPath = linePath(scenario, width, height, minValue, maxValue);

  return (
    <div className="future-chart-wrap">
      <svg className="future-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Future projection chart">
        <path d={baselinePath} className="line-baseline" />
        <path d={scenarioPath} className="line-scenario" />
      </svg>
      <div className="legend-row">
        <span className="legend-item"><i className="dot-baseline" />Current path</span>
        <span className="legend-item"><i className="dot-scenario" />Your scenario</span>
      </div>
    </div>
  );
}

export default function Page() {
  const [token, setToken] = useState("finmaxxin-demo-token");
  const [userId, setUserId] = useState("user-123");
  const [horizon, setHorizon] = useState(36);
  const [incomeChange, setIncomeChange] = useState(5);
  const [spendChange, setSpendChange] = useState(2);
  const [debtExtra, setDebtExtra] = useState(500);
  const [homePrice, setHomePrice] = useState(0);
  const [homeDown, setHomeDown] = useState(0);
  const [homeMonth, setHomeMonth] = useState(12);

  const [scenarioId, setScenarioId] = useState("");
  const [decisionId, setDecisionId] = useState("");
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [previews, setPreviews] = useState<Record<string, ExecutionPreview>>({});
  const [executionResults, setExecutionResults] = useState<Record<string, ExecutionResult>>({});
  const [actionMessages, setActionMessages] = useState<Record<string, string>>({});
  const [trace, setTrace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-User-Id": userId,
    }),
    [token, userId]
  );

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(body || `HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  }

  async function createAndSimulate() {
    setBusy(true);
    setError("");
    try {
      const assumptions: Record<string, unknown> = {
        income_change_pct: incomeChange,
        monthly_spend_change_pct: spendChange,
        debt_plan: { extra_payment_monthly: { amount_cents: Math.round(debtExtra * 100), currency: "CAD" } },
      };
      if (homePrice > 0 && homeDown > 0) {
        assumptions.home_purchase = {
          price: { amount_cents: Math.round(homePrice * 100), currency: "CAD" },
          down_payment: { amount_cents: Math.round(homeDown * 100), currency: "CAD" },
          target_month: homeMonth,
        };
      }

      const create = await request<{ scenario_id: string }>("/v1/scenarios", {
        method: "POST",
        body: JSON.stringify({
          user_id: userId,
          horizon_months: horizon,
          assumptions,
        }),
      });
      setScenarioId(create.scenario_id);

      const sim = await request<SimulationResult>(`/v1/scenarios/${create.scenario_id}/simulate`, { method: "POST" });
      setDecisionId(sim.decision_id);
      setSimulation(sim);

      const rec = await request<{ recommendations: Recommendation[] }>(`/v1/scenarios/${create.scenario_id}/recommendations`);
      setRecommendations(rec.recommendations);
      setPreviews({});
      setExecutionResults({});
      setActionMessages({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function previewAction(rec: Recommendation) {
    setBusy(true);
    setError("");
    try {
      const preview = await request<ExecutionPreview>("/v1/actions/preview", {
        method: "POST",
        body: JSON.stringify({
          scenario_id: scenarioId,
          recommendation_id: rec.recommendation_id,
          action_type: rec.action_type,
        }),
      });
      setPreviews((prev) => ({ ...prev, [rec.recommendation_id]: preview }));
      setActionMessages((prev) => ({
        ...prev,
        [rec.recommendation_id]: `Preview ready: 12m impact ${cad(preview.projected_impact_12m.amount_cents)}; fees ${cad(preview.fees.amount_cents)}.`,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function executeAction(recId: string) {
    const preview = previews[recId];
    if (!preview) return;
    setBusy(true);
    setError("");
    try {
      const execution = await request<ExecutionResult>("/v1/actions/execute", {
        method: "POST",
        body: JSON.stringify({
          preview_id: preview.preview_id,
          action_id: preview.action_id,
          confirm: true,
          idempotency_key: `idem-${preview.preview_id}`,
        }),
      });
      setExecutionResults((prev) => ({ ...prev, [recId]: execution }));
      setActionMessages((prev) => ({
        ...prev,
        [recId]: `Execution accepted at ${new Date(execution.executed_at).toLocaleString()} (id: ${execution.execution_id.slice(0, 8)}...).`,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function loadTrace() {
    if (!decisionId) return;
    setBusy(true);
    setError("");
    try {
      const payload = await request<Record<string, unknown>>(`/v1/decisions/${decisionId}/trace`);
      setTrace(JSON.stringify(payload, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  const primaryRecommendation = recommendations[0] || null;
  const alternativeRecommendations = recommendations.slice(1);

  return (
    <main className="shell">
      <h1 className="headline">Finmaxxin: See Your Financial Future Before You Act</h1>
      <p className="sub">Compare your current path to a custom scenario, then take the best next action with clear impact and risk context.</p>

      <div className="grid">
        <section className="panel">
          <h2>Inputs</h2>
          <div className="row">
            <div>
              <label>User ID</label>
              <input value={userId} onChange={(e) => setUserId(e.target.value)} />
            </div>
            <div>
              <label>Bearer token</label>
              <input value={token} onChange={(e) => setToken(e.target.value)} />
            </div>
          </div>

          <div className="row">
            <div>
              <label>Horizon (months)</label>
              <input
                type="number"
                min={1}
                max={60}
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
              />
            </div>
            <div>
              <label>Income change (%)</label>
              <input type="number" value={incomeChange} onChange={(e) => setIncomeChange(Number(e.target.value))} />
            </div>
          </div>

          <div className="row">
            <div>
              <label>Spend change (%)</label>
              <input type="number" value={spendChange} onChange={(e) => setSpendChange(Number(e.target.value))} />
            </div>
            <div>
              <label>Debt extra payment (CAD/month)</label>
              <input type="number" value={debtExtra} onChange={(e) => setDebtExtra(Number(e.target.value))} />
            </div>
          </div>

          <label>Home purchase price (optional CAD)</label>
          <input type="number" value={homePrice} onChange={(e) => setHomePrice(Number(e.target.value))} />
          <div className="row">
            <div>
              <label>Down payment (CAD)</label>
              <input type="number" value={homeDown} onChange={(e) => setHomeDown(Number(e.target.value))} />
            </div>
            <div>
              <label>Target month</label>
              <input type="number" min={1} max={60} value={homeMonth} onChange={(e) => setHomeMonth(Number(e.target.value))} />
            </div>
          </div>

          <button disabled={busy} onClick={createAndSimulate}>
            Build my future projection
          </button>

          <p className="meta">{scenarioId ? `Scenario ID: ${scenarioId}` : "No scenario yet"}</p>
          <p className="meta">Start with your best estimate, then iterate assumptions to compare futures.</p>
          {error ? <p className="meta" style={{ color: "#b00020" }}>{error}</p> : null}
        </section>

        <section className="panel">
          <h2>Your Future At A Glance</h2>
          {simulation ? (
            <>
              <p>{projectionVerdict(simulation)}</p>
              <MetricWithHelp
                label="Current path at horizon"
                value={cad(simulation.baseline_final_net_worth_cents)}
                help="This baseline keeps your current profile and projects forward without the scenario changes."
              />
              <MetricWithHelp
                label="Scenario path at horizon"
                value={cad(simulation.scenario_final_net_worth_cents)}
                help="This applies your inputs (income/spend/debt/home timing changes) over the same period."
              />
              <MetricWithHelp
                label="Most likely difference"
                value={cad(simulation.delta_final_net_worth_cents)}
                help="Median difference between scenario and baseline at the end of the horizon."
              />
              <MetricWithHelp
                label="Chance scenario wins"
                value={`${(simulation.scenario_beats_baseline_probability * 100).toFixed(1)}%`}
                help="Percentage of simulations where your scenario finishes ahead of the current path."
              />
              <FutureChart baseline={simulation.baseline_timeline.p50_cents} scenario={simulation.timeline.p50_cents} />
            </>
          ) : (
            <p className="meta">Run a projection to see baseline vs scenario results here.</p>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Best Next Action</h2>
        {primaryRecommendation ? (
          <article className="card">
            <h3>{primaryRecommendation.title}</h3>
            <span className="pill">
              fit score {primaryRecommendation.score.toFixed(2)} | {primaryRecommendation.risk_level} risk
            </span>
            <MetricWithHelp
              label="Expected delta"
              value={`${cad(primaryRecommendation.expected_net_worth_delta.amount_cents)} over ${horizon} months`}
              help="Median projected change in your net worth versus staying on your current path."
            />
            <MetricWithHelp
              label="P10 downside"
              value={cad(primaryRecommendation.downside_p10_delta.amount_cents)}
              help="Stress-case outcome: about 1 in 10 simulations landed at or below this delta."
            />
            <MetricWithHelp
              label="Confidence"
              value={`${(primaryRecommendation.confidence * 100).toFixed(1)}% (${confidenceBand(primaryRecommendation.confidence)})`}
              help="How stable this estimate is across simulations, based on outcome consistency and result spread."
            />
            <p>{primaryRecommendation.rationale[0]}</p>
            <div className="row">
              <button disabled={busy} onClick={() => previewAction(primaryRecommendation)}>
                Preview impact
              </button>
              <button
                disabled={busy || !previews[primaryRecommendation.recommendation_id]}
                onClick={() => executeAction(primaryRecommendation.recommendation_id)}
              >
                Execute action
              </button>
            </div>
            {previews[primaryRecommendation.recommendation_id] ? (
              <p className="meta">
                Preview: 12m impact {cad(previews[primaryRecommendation.recommendation_id].projected_impact_12m.amount_cents)}; fees{" "}
                {cad(previews[primaryRecommendation.recommendation_id].fees.amount_cents)}.
              </p>
            ) : null}
            {actionMessages[primaryRecommendation.recommendation_id] ? (
              <p className="meta">{actionMessages[primaryRecommendation.recommendation_id]}</p>
            ) : null}
          </article>
        ) : (
          <p className="meta">Generate a projection first to get a prioritized next action.</p>
        )}

        {alternativeRecommendations.length > 0 ? (
          <details className="alt-actions">
            <summary>Alternative actions ({alternativeRecommendations.length})</summary>
            <div className="cards">
              {alternativeRecommendations.map((rec) => (
                <article className="card" key={rec.recommendation_id}>
                  <h3>{rec.title}</h3>
                  <p className="meta">
                    Expected {cad(rec.expected_net_worth_delta.amount_cents)} | Confidence {(rec.confidence * 100).toFixed(1)}%
                  </p>
                </article>
              ))}
            </div>
          </details>
        ) : null}
      </section>

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>How This Projection Is Calculated</h2>
        <p className="meta">
          Baseline keeps your current profile unchanged. Scenario applies your edited inputs. Both are projected over your selected
          horizon across many simulated market paths, then summarized into likely outcomes and downside ranges.
        </p>
      </section>

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Decision Trace</h2>
        <div className="row">
          <input value={decisionId} onChange={(e) => setDecisionId(e.target.value)} placeholder="decision-id" />
          <button disabled={busy || !decisionId} onClick={loadTrace}>
            Load trace
          </button>
        </div>
        <div className="trace">{trace || "No trace loaded."}</div>
      </section>
    </main>
  );
}
