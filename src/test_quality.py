from src.quality import quality_check
from src.formatter import format_story

item={
"title":"Major earthquake strikes region",
"summary":"Officials are assessing the situation and emergency teams are responding.",
"source":"Test Source","url":"https://example.com/story",
"confidence":"high","score":90,"primary_source":True,
"corroborating_sources":2,"strong_corroboration":2,
"event_status":"NEW","event_id":"test-event","language_status":"ENGLISH"
}
out=format_story(item); item.update(out)
r=quality_check(item)
assert r["quality_pass"],r
assert len(item["post"])<=280
assert 3 <= len(item["post"].split(". ")) <= 4
print("QUALITY TEST PASSED")
