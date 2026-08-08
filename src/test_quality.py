from src.quality import quality_check
from src.formatter import format_story


item = {
    "title": "Major earthquake strikes region",
    "summary": (
        "Officials are assessing the situation and "
        "emergency teams are responding."
    ),
    "source": "Test Source",
    "url": "https://example.com/story",
    "confidence": "high",
    "score": 90,
    "primary_source": True,
    "corroborating_sources": 2,
    "strong_corroboration": 2,
    "event_status": "NEW",
    "event_id": "test-event",
    "language_status": "ENGLISH",
}


out = format_story(item)
item.update(out)

r = quality_check(item)

assert r["quality_pass"], r

if item["format"] == "single":
    assert len(item["post"]) <= 270
    assert item["post"].strip()
    assert "Source:" in item["post"]
else:
    assert item["thread"]
    for post in item["thread"]:
        assert len(post) <= 270
        assert post.strip()

print("QUALITY TEST PASSED")
