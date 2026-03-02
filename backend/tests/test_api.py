from fastapi.testclient import TestClient

from app.main import create_app


def headers(user_id: str = "user-123") -> dict[str, str]:
    return {
        "Authorization": "Bearer finmaxxin-demo-token",
        "X-User-Id": user_id,
    }


def test_end_to_end_flow() -> None:
    client = TestClient(create_app())

    create_payload = {
        "user_id": "user-123",
        "horizon_months": 36,
        "assumptions": {
            "income_change_pct": 5,
            "monthly_spend_change_pct": 2,
            "debt_plan": {
                "extra_payment_monthly": {"amount_cents": 50000, "currency": "CAD"},
            },
        },
    }
    create_res = client.post("/v1/scenarios", json=create_payload, headers=headers())
    assert create_res.status_code == 201
    scenario_id = create_res.json()["scenario_id"]

    sim_res = client.post(f"/v1/scenarios/{scenario_id}/simulate", headers=headers())
    assert sim_res.status_code == 200
    decision_id = sim_res.json()["decision_id"]

    rec_res = client.get(f"/v1/scenarios/{scenario_id}/recommendations", headers=headers())
    assert rec_res.status_code == 200
    recommendations = rec_res.json()["recommendations"]
    assert len(recommendations) > 0
    top_recommendation = recommendations[0]

    preview_payload = {
        "scenario_id": scenario_id,
        "recommendation_id": top_recommendation["recommendation_id"],
        "action_type": top_recommendation["action_type"],
    }
    preview_res = client.post("/v1/actions/preview", json=preview_payload, headers=headers())
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["requires_confirmation"] is True

    execute_payload = {
        "preview_id": preview["preview_id"],
        "action_id": preview["action_id"],
        "confirm": True,
        "idempotency_key": "idem-key-12345",
    }
    execute_res = client.post("/v1/actions/execute", json=execute_payload, headers=headers())
    assert execute_res.status_code == 200
    execution = execute_res.json()
    assert execution["status"] == "accepted"

    replay_res = client.post("/v1/actions/execute", json=execute_payload, headers=headers())
    assert replay_res.status_code == 200
    assert replay_res.json()["execution_id"] == execution["execution_id"]

    trace_res = client.get(f"/v1/decisions/{decision_id}/trace", headers=headers())
    assert trace_res.status_code == 200
    trace = trace_res.json()
    assert trace["decision_id"] == decision_id
    assert "feature_contributions" in trace
    assert "policy_checks" in trace

    advisor_res = client.post(f"/v1/scenarios/{scenario_id}/advisor-brief", headers=headers())
    assert advisor_res.status_code == 200
    advisor = advisor_res.json()
    assert advisor["scenario_id"] == scenario_id
    assert advisor["decision_id"] == decision_id
    assert "Verdict:" in advisor["advice_text"]
    assert "Suggested down payment:" in advisor["advice_text"]
    assert "Primary action:" in advisor["advice_text"]
    assert isinstance(advisor["fallback_used"], bool)


def test_requires_bearer_token() -> None:
    client = TestClient(create_app())
    response = client.post("/v1/scenarios", json={"user_id": "user-123", "horizon_months": 12, "assumptions": {}})
    assert response.status_code == 401


def test_advisor_requires_simulation_first() -> None:
    client = TestClient(create_app())
    create_payload = {"user_id": "user-123", "horizon_months": 24, "assumptions": {}}
    create_res = client.post("/v1/scenarios", json=create_payload, headers=headers())
    assert create_res.status_code == 201
    scenario_id = create_res.json()["scenario_id"]

    advisor_res = client.post(f"/v1/scenarios/{scenario_id}/advisor-brief", headers=headers())
    assert advisor_res.status_code == 400
