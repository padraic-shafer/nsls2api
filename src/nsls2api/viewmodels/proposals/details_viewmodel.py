
from starlette.requests import Request

from nsls2api.models.proposals import Proposal
from nsls2api.services import proposal_service
from nsls2api.viewmodels.shared.viewmodelbase import ViewModelBase


class DetailsViewModel(ViewModelBase):
    def __init__(self, proposal_id: str, request: Request):
        super().__init__(request)

        self.proposal_id = proposal_id
        self.proposal: Proposal | None = None

    async def load(self):
        self.proposal = await proposal_service.proposal_by_id(self.proposal_id)
