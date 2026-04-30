from services.shared.citation_grounding import ground_citations

def test_correct_citation():
    answer = "The LCR is 118.5% [1] which is above the minimum."
    sources = [{"text": "Current LCR ratio: 118.5%, above regulatory minimum of 100%"}]
    report = ground_citations(answer, sources)
    assert report.total_citations == 1
    assert report.verified == 1
    assert report.accuracy == 1.0

def test_wrong_citation():
    answer = "The NSFR is 104.2% [1] as reported."
    sources = [{"text": "The headcount increased by 15 employees in Q3."}]
    report = ground_citations(answer, sources)
    assert report.total_citations == 1
    assert report.unverified == 1
    assert report.accuracy == 0.0

def test_no_citations():
    answer = "The LCR looks fine."
    sources = [{"text": "LCR: 118.5%"}]
    report = ground_citations(answer, sources)
    assert report.total_citations == 0
    assert report.accuracy == 1.0

def test_multiple_citations():
    answer = "LCR is 118.5% [1] and NSFR is 104.2% [2]."
    sources = [
        {"text": "LCR ratio: 118.5%"},
        {"text": "NSFR: 104.2% stable"},
    ]
    report = ground_citations(answer, sources)
    assert report.total_citations == 2
    assert report.verified == 2
