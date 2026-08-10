
from fastapi import Request

from nsls2api.models.proposals import Proposal
from nsls2api.services import proposal_service
from nsls2api.viewmodels.shared.viewmodelbase import ViewModelBase


class SearchViewModel(ViewModelBase):
    def __init__(self, request: Request):
        super().__init__(request)

        self.proposals: list[Proposal] | None = []
        self.request = request

        # self.search_text: str = request
        #
        # print(f"search_text={self.search_text}")
        print(f"query_params:{request.query_params}")

        try:
            self.search_text = request.query_params["search_text"]
        except KeyError:
            self.search_text = ""

    async def load(self):
        print(f"Searching for {self.search_text}")
        self.proposals = await proposal_service.search_proposals(self.search_text)
