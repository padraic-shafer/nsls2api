
from starlette.requests import Request

from nsls2api.api.models.proposal_model import ProposalDiagnostics
from nsls2api.services import proposal_service
from nsls2api.viewmodels.proposals.details_viewmodel import DetailsViewModel


class ProposalDiagnosticsViewModel(DetailsViewModel):
    def __init__(self, proposal_id: str, request: Request):
        super().__init__(proposal_id, request)

        self.proposal_id = proposal_id
        self.proposal: ProposalDiagnostics | None = None
        self.diagnostic_message: str | None = None

    async def load(self):
        try:
            self.proposal = await proposal_service.diagnostic_details_by_id(
                self.proposal_id
            )
        except LookupError as error:
            self.error = f"{error}"
