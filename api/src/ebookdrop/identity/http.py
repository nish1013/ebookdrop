"""Identity endpoints."""

from typing import Annotated

from fastapi import APIRouter, Cookie, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ebookdrop.identity.domain import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    SESSION_LENGTH,
    EmailTakenError,
    IdentityError,
    InvalidEmailError,
    SignedOutError,
    TooManyAttemptsError,
    WrongEmailOrPasswordError,
)
from ebookdrop.identity.service import IdentityService

SESSION_COOKIE = "session"

_ANSWERS: dict[type[IdentityError], tuple[int, str]] = {
    InvalidEmailError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_email"),
    EmailTakenError: (status.HTTP_409_CONFLICT, "email_taken"),
    WrongEmailOrPasswordError: (
        status.HTTP_401_UNAUTHORIZED,
        "wrong_email_or_password",
    ),
    TooManyAttemptsError: (status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts"),
    SignedOutError: (status.HTTP_401_UNAUTHORIZED, "signed_out"),
}


class SignUpIn(BaseModel):
    """A sign-up request."""

    email: str
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class SignInIn(BaseModel):
    """A sign-in request."""

    email: str
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class ReaderOut(BaseModel):
    """A reader as the pages see it."""

    email: str


class ErrorOut(BaseModel):
    """A refused request. `code` names the reason."""

    code: str


SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def add_identity(app: FastAPI, service: IdentityService) -> None:
    """Add the identity endpoints and their error answers to the app."""
    router = APIRouter(prefix="/api", responses={422: {"model": ErrorOut}})

    @router.post(
        "/accounts",
        status_code=status.HTTP_201_CREATED,
        responses={409: {"model": ErrorOut}},
    )
    def sign_up(body: SignUpIn) -> ReaderOut:
        return ReaderOut(email=service.sign_up(body.email, body.password).value)

    @router.post(
        "/sessions",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={401: {"model": ErrorOut}, 429: {"model": ErrorOut}},
    )
    def sign_in(body: SignInIn, response: Response) -> None:
        token = service.sign_in(body.email, body.password)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(SESSION_LENGTH.total_seconds()),
            httponly=True,
            secure=True,
            samesite="lax",
        )

    @router.get("/sessions/current", responses={401: {"model": ErrorOut}})
    def current(session: SessionCookie = None) -> ReaderOut:
        email = service.signed_in_email(session) if session else None
        if email is None:
            raise SignedOutError
        return ReaderOut(email=email)

    @router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT)
    def sign_out(response: Response, session: SessionCookie = None) -> None:
        if session:
            service.sign_out(session)
        response.delete_cookie(
            SESSION_COOKIE, httponly=True, secure=True, samesite="lax"
        )

    @app.exception_handler(IdentityError)
    def refuse(_: Request, err: IdentityError) -> JSONResponse:
        code, reason = _ANSWERS[type(err)]
        return JSONResponse({"code": reason}, status_code=code)

    app.include_router(router)
