
from starlette.requests import Request


class ViewModelBase:
    def __init__(self, request: Request):
        self.request: Request = request
        self.is_htmx_request = request.headers.get("HX-Request")

        self.error: str | None = None
        self.view_model = self.to_dict()

    def to_dict(self) -> dict:
        return self.__dict__
