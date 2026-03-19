

from langgraph.graph import StateGraph, END

from src.domain.enums import WorkflowStatus
from src.workflows.langgraph.state import ReceiptWorkflowState

def build_graph():

    graph = StateGraph(ReceiptWorkflowState)

    # graph.add_node("ingest", ingest_node)
    # graph.add_node("extract", extract_node)
    # graph.add_node("enrich", enrich_node)
    # graph.add_node("validate", validate_node)
    # graph.add_node("review", review_node)
    # graph.add_node("commit", commit_node)

    # graph.set_entry_point("ingest")

    # graph.add_edge("ingest", "extract")

    # graph.add_edge("extract", "enrich")

    # graph.add_edge("enrich", "validate")

    # graph.add_conditional_edges(
    #     "validate",
    #     lambda state: "review" if state["requires_review"] else "commit"
    # )

    # graph.add_edge("review", "commit")

    # graph.add_edge("commit", END)

    return graph.compile()