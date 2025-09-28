from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

@dataclass
class AnalysisIssue:
	code: str
	timestamp: datetime
	value: Optional[str] = None

@dataclass
class AnalysisResult:
    phase_metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[AnalysisIssue] = field(default_factory=list)
