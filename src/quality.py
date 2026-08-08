import re

def sentence_count(text):
    return len(re.findall(r"(?<=[.!?])\s+", (text or "").strip())) + (1 if (text or "").strip() else 0)

def quality_check(item):
    errors=[]; warnings=[]
    fmt=item.get("format")
    if fmt=="single":
        post=item.get("post","")
        if not post: errors.append("empty post")
        if len(post)>280: errors.append("single post exceeds 280 characters")
        if sentence_count(post)<3: errors.append("single post has fewer than 3 sentences")
    elif fmt=="thread":
        thread=item.get("thread",[])
        if not thread: errors.append("empty thread")
        if len(thread)>7: errors.append("thread too long")
        for i,p in enumerate(thread,1):
            if not p.strip(): errors.append(f"thread post {i} is empty")
            if len(p)>280: errors.append(f"thread post {i} exceeds 280 characters")
    else:
        errors.append("unknown format")

    if item.get("language_status") not in ("ENGLISH","TRANSLATED_TO_ENGLISH"):
        errors.append("final language is not English")
    if not item.get("url","").startswith(("http://","https://")):
        errors.append("invalid source URL")
    if item.get("confidence")=="low":
        warnings.append("low-confidence story")
    if re.search(r"\bconfirmed\b", item.get("post","").lower()) and item.get("confidence")=="low":
        errors.append("low-confidence story uses confirmed wording")
    return {"quality_pass":not errors,"quality_errors":errors,"quality_warnings":warnings}
