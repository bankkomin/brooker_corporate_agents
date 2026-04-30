from services.shared.calibrated_confidence import compute_confidence

def test_high_confidence():
    result = compute_confidence(
        retrieved_chunks=[{"text": "LCR is 118.5%"}] * 5,
        top_similarity=0.92,
        answer_text="LCR is 118.5%",
        proposed_value="118.5",
        citation_accuracy=1.0,
        historical_approval_rate=0.95,
    )
    assert result.label == "High"
    assert result.composite >= 0.75

def test_low_confidence_no_sources():
    result = compute_confidence(
        retrieved_chunks=[],
        top_similarity=0.0,
        answer_text="I'm not sure about the LCR.",
        citation_accuracy=0.0,
    )
    assert result.label == "Low"
    assert result.composite < 0.5

def test_medium_confidence():
    result = compute_confidence(
        retrieved_chunks=[{"text": "Some data"}] * 2,
        top_similarity=0.65,
        answer_text="The rate appears to be 3.15%",
        proposed_value="3.15",
        citation_accuracy=0.5,
    )
    assert result.label == "Medium"

def test_verbatim_boosts_confidence():
    result_with = compute_confidence(
        retrieved_chunks=[{"text": "Rate: 3.15%"}],
        top_similarity=0.7,
        answer_text="Rate is 3.15%",
        proposed_value="3.15",
    )
    result_without = compute_confidence(
        retrieved_chunks=[{"text": "Rate around 3%"}],
        top_similarity=0.7,
        answer_text="Rate is 3.15%",
        proposed_value="3.15",
    )
    assert result_with.verbatim_score > result_without.verbatim_score
