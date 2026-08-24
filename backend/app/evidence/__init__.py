"""证据链：recorder（结论 → 数据来源可回溯）。"""

from .recorder import EvidenceChain, EvidenceEntry, build_chain, get_chain, recent_chains, summarize_chain

__all__ = [
    "EvidenceChain",
    "EvidenceEntry",
    "build_chain",
    "get_chain",
    "recent_chains",
    "summarize_chain",
]
