from app.models import DecisionAIOutput, DecisionStatus, Quality


def mock_ai_decision() -> DecisionAIOutput:
    return DecisionAIOutput(
        decision=DecisionStatus.go,
        confidence=78,
        quality=Quality.a,
        why=["Contexte propre", "RR suffisant", "Spread OK"],
        notes="Mock IA",
    )
