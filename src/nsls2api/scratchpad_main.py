# This file is just a place to play and test stuff while I am messing about
# This is not intended to be a long lived or permanent file.

from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


async def common_parameters(
    q: str | None = None, skip: int = 0, limit: int = 100
):
    return {"q": q, "skip": skip, "limit": limit}


@app.get("/items/")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    commons["stuart"] = "awesome"
    return commons


@app.get("/users/")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return commons
