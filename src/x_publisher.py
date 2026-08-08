import os
import requests

class XPublisherError(Exception):
    pass

class XPublisher:
    """
    Official X API v2 adapter.
    Disabled unless X_PUBLISH_ENABLED=true.

    The API currently uses pay-per-use pricing, so this adapter does not
    pretend that live X publishing is free.
    """
    def __init__(self):
        self.enabled=os.getenv("X_PUBLISH_ENABLED","false").lower()=="true"
        self.token=os.getenv("X_USER_ACCESS_TOKEN","").strip()
        self.base="https://api.x.com/2/tweets"

    def _headers(self):
        if not self.token:
            raise XPublisherError("Missing X_USER_ACCESS_TOKEN")
        return {
            "Authorization":f"Bearer {self.token}",
            "Content-Type":"application/json"
        }

    def create_post(self,text,reply_to=None):
        if not self.enabled:
            return {"mode":"dry_run","text":text}
        payload={"text":text}
        if reply_to:
            payload["reply"]={"in_reply_to_tweet_id":reply_to}
        r=requests.post(self.base,headers=self._headers(),json=payload,timeout=20)
        if r.status_code>=300:
            raise XPublisherError(f"X API HTTP {r.status_code}: {r.text[:500]}")
        return r.json()

    def publish(self,item):
        if item.get("format")=="single":
            return [self.create_post(item["post"])]

        ids=[]
        previous=None
        for text in item.get("thread",[]):
            result=self.create_post(text,previous)
            ids.append(result)
            previous=(result.get("data") or {}).get("id")
        return ids
