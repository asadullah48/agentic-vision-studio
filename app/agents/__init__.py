"""Multi-agent vision system.

Four single-responsibility agents, coordinated by the orchestrator:

    PerceptionAgent      measures the image
    FormatReasoningAgent plans the encode
    ImageTransformAgent  executes it
    VisionCriticAgent    audits the result and can force a retry
"""

from .critic import QualityAudit, VisionCriticAgent
from .orchestrator import ChatAgentResponse, PipelineExecution, VisionOrchestrator
from .perception import PerceptionAgent, PerceptionReport
from .reasoner import FormatReasoningAgent, StrategyDecision
from .transformer import ImageTransformAgent, TransformOutput, TransformResult

__all__ = [
    "ChatAgentResponse",
    "FormatReasoningAgent",
    "ImageTransformAgent",
    "PerceptionAgent",
    "PerceptionReport",
    "PipelineExecution",
    "QualityAudit",
    "StrategyDecision",
    "TransformOutput",
    "TransformResult",
    "VisionCriticAgent",
    "VisionOrchestrator",
]
