from pathlib import Path

import fastapi
from fastapi import HTTPException, status
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from nsls2api.viewmodels.diagnostics.proposal_viewmodel import (
    ProposalDiagnosticsViewModel,
)
from nsls2api.viewmodels.diagnostics.user_viewmodel import (
    UserDiagnosticsViewModel,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
router = fastapi.APIRouter()


@router.get("/diagnostics/username/{username}", include_in_schema=False)
async def diag_username(username: str, request: Request):
    vm = UserDiagnosticsViewModel(username, request)
    await vm.load()

    # if there was a problem in getting the information for a user then the error will not be None.
    if vm.error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=vm.error)

    print(vm.to_dict())

    return templates.TemplateResponse("diagnostics/user_diagnostics.html", vm.to_dict())


@router.get("/diagnostics/proposal/{proposal_id}", include_in_schema=False)
async def diag_proposal(proposal_id: str, request: Request):
    vm = ProposalDiagnosticsViewModel(proposal_id, request)

    try:
        await vm.load()
    except Exception as e:
        print(f"Exception: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # if there was a problem in getting the information for a user then the error will not be None.
    if vm.error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=vm.error)

    print(vm.to_dict())

    return templates.TemplateResponse(
        "diagnostics/proposal_diagnostics.html", vm.to_dict()
    )
