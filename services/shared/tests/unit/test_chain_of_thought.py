from services.shared.chain_of_thought import classify_complexity, build_cot_prompt, parse_cot_response

def test_simple_query():
    assert classify_complexity("What is the LCR?") == "simple"

def test_comparison_query():
    assert classify_complexity("Compare Q2 vs Q3 capital adequacy") == "comparison"

def test_calculation_query():
    assert classify_complexity("Calculate the headroom above covenant threshold") == "calculation"

def test_analytical_query():
    assert classify_complexity("Why did the NSFR decline this quarter?") == "analytical"

def test_trend_query():
    assert classify_complexity("How has LCR trended over time?") == "analytical"

def test_simple_prompt_no_steps():
    prompt = build_cot_prompt("What is the LCR?", "simple", "LCR: 118.5%")
    assert "Step 1" not in prompt
    assert "LCR: 118.5%" in prompt

def test_comparison_prompt_has_steps():
    prompt = build_cot_prompt("Compare Q2 vs Q3", "comparison", "context")
    assert "Step 1" in prompt
    assert "COMPARE" in prompt

def test_parse_cot_extracts_steps():
    response = """**Step 1 - Identify:** Comparing LCR across quarters
**Step 2 - Data:** Q2 LCR=115%, Q3 LCR=118.5%
**Step 3 - Compare:** LCR improved by 3.5 percentage points
**Answer:** LCR improved from 115% in Q2 to 118.5% in Q3, a 3.5pp increase."""

    result = parse_cot_response(response, "Compare Q2 vs Q3 LCR", "comparison")
    assert result.used_cot is True
    assert len(result.steps) == 3
    assert "118.5%" in result.final_answer

def test_parse_simple_no_steps():
    result = parse_cot_response("LCR is 118.5%", "What is LCR?", "simple")
    assert result.used_cot is False
    assert result.steps == []
