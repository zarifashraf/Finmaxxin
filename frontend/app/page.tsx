"use client";

import { useMemo, useState } from "react";

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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function cad(cents: number) {
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(
    cents / 100
  );
}

export default function Page() {
  const [token, setToken] = useState("yousim-demo-token");
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
  const [simulationSummary, setSimulationSummary] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [previews, setPreviews] = useState<Record<string, ExecutionPreview>>({});
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

      const sim = await request<{
        decision_id: string;
        baseline_final_net_worth_cents: number;
        scenario_final_net_worth_cents: number;
        delta_final_net_worth_cents: number;
        downside_p10_delta_cents: number;
      }>(`/v1/scenarios/${create.scenario_id}/simulate`, { method: "POST" });
      setDecisionId(sim.decision_id);
      setSimulationSummary(
        `Baseline ${cad(sim.baseline_final_net_worth_cents)} | Scenario ${cad(sim.scenario_final_net_worth_cents)} | Median delta ${cad(sim.delta_final_net_worth_cents)} | P10 downside ${cad(sim.downside_p10_delta_cents)}`
      );

      const rec = await request<{ recommendations: Recommendation[] }>(`/v1/scenarios/${create.scenario_id}/recommendations`);
      setRecommendations(rec.recommendations);
      setPreviews({});
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
      await request("/v1/actions/execute", {
        method: "POST",
        body: JSON.stringify({
          preview_id: preview.preview_id,
          action_id: preview.action_id,
          confirm: true,
          idempotency_key: `idem-${preview.preview_id}`,
        }),
      });
      alert("Execution accepted.");
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

  return (
    <main className="shell">
      <h1 className="headline">YouSim: Personal Financial Digital Twin</h1>
      <p className="sub">Model major life decisions across 0-5 years, then safely execute recommended actions.</p>

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
            Create scenario, simulate, and rank recommendations
          </button>

          <p className="meta">{scenarioId ? `Scenario ID: ${scenarioId}` : "No scenario yet"}</p>
          <p className="meta">{simulationSummary || "No simulation output yet"}</p>
          {error ? <p className="meta" style={{ color: "#b00020" }}>{error}</p> : null}
        </section>

        <section className="panel">
          <h2>Recommendations</h2>
          <div className="cards">
            {recommendations.map((rec) => {
              const preview = previews[rec.recommendation_id];
              return (
                <article className="card" key={rec.recommendation_id}>
                  <h3>{rec.title}</h3>
                  <span className="pill">
                    score {rec.score.toFixed(2)} | {rec.risk_level}
                  </span>
                  <p>Expected delta: {cad(rec.expected_net_worth_delta.amount_cents)}</p>
                  <p>P10 downside: {cad(rec.downside_p10_delta.amount_cents)}</p>
                  <p>Confidence: {(rec.confidence * 100).toFixed(1)}%</p>
                  <p>{rec.rationale[0]}</p>
                  <div className="row">
                    <button disabled={busy} onClick={() => previewAction(rec)}>
                      Preview action
                    </button>
                    <button disabled={busy || !preview} onClick={() => executeAction(rec.recommendation_id)}>
                      Execute action
                    </button>
                  </div>
                  {preview ? (
                    <p>
                      12m impact {cad(preview.projected_impact_12m.amount_cents)} | fees {cad(preview.fees.amount_cents)}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      </div>

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
