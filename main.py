import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VoteRequest(BaseModel):
    score: int = Field(..., ge=1, le=5)


@app.get("/")
def read_root():
    return {"message": "Feedback API running"}


@app.post("/api/feedback")
async def submit_feedback(vote: VoteRequest) -> Dict[str, Any]:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    now = datetime.now(timezone.utc)
    data = {"score": vote.score, "created_at": now, "updated_at": now}
    create_document("feedback", data)
    return {"ok": True, "message": "Thanks for your feedback!"}


@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    docs = get_documents("feedback")
    # Aggregate counts per score
    counts = {str(i): 0 for i in range(1, 6)}
    total_score = 0
    timeline: List[Dict[str, Any]] = []

    for d in docs:
        s = int(d.get("score", 0))
        if 1 <= s <= 5:
            counts[str(s)] += 1
            total_score += s
            ts = d.get("created_at")
            # ensure ISO string
            if isinstance(ts, datetime):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)
            timeline.append({"timestamp": ts_str, "score": s})

    total_votes = sum(counts.values())

    return {
        "counts": counts,
        "total_votes": total_votes,
        "total_score": total_score,
        "timeline": sorted(timeline, key=lambda x: x["timestamp"]),
    }


@app.delete("/api/reset")
async def reset_votes() -> Dict[str, Any]:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    db["feedback"].delete_many({})
    return {"ok": True}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        from database import db as _db
        
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
