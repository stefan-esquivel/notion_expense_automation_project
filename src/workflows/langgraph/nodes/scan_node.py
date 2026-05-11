
from logging import Logger
from logger import get_logger
from src.domain.enums import WorkflowStatus
from src.workflows.langgraph.state import ReceiptWorkflowState

logger: Logger = get_logger(name=__name__)


def scan_node(state: ReceiptWorkflowState) -> ReceiptWorkflowState:

    """
    Args:
        state: Current workflow state with receipt data


        Returns:

        Updated state with receipt data
        """

    state['status'] = WorkflowStatus.SCANNING

    try:

        state.scanning_results.has_missing_data = True
        
        return state

    except Exception as e:

        state['status'] = WorkflowStatus.FAILED
        state['failure_reason'] = f"Enrichment failed: {str(e)}"
        logger.error(msg=f"x Enrichment failed: {e}")

        return state

    