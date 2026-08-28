import httpx

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class TokenVerificationError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def verify_access_token(access_token: str) -> dict:
    """Ask Google whether an access token is valid and return its metadata.

    Raises TokenVerificationError (401) for an invalid/expired token, or
    (502) if Google's tokeninfo endpoint couldn't be reached.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                GOOGLE_TOKENINFO_URL, params={"access_token": access_token}
            )
        except httpx.HTTPError as exc:
            raise TokenVerificationError(
                502, "Could not reach Google to verify the access token."
            ) from exc

    if response.status_code != 200:
        raise TokenVerificationError(401, "Google access token is invalid or expired.")

    return response.json()
