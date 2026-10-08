from pydantic import BaseModel, Field
from typing import List, Optional

class JobPosting(BaseModel):
    id: str
    position: str
    company: str
    location: Optional[str] = "Remote"
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = ""
    url: str
    source: str = "remoteok"