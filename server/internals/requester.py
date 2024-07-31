"""
Contains the Requester class.
"""
# Standard Library Imports
from hashlib import sha512
from time import time
from typing import Any, Callable, Optional
from uuid import uuid4
from threading import Lock

# Third Party Imports
from requests import Response, delete, get, post, put, HTTPError

# Internal Imports
from .clogging import createLogger
from .config import Config


# Create cache variables
cacheLock: Lock = Lock()
cacheLastChecked: float = time()

# Create cache dictionary
cache: dict[str, dict] = {}


class RBadGateway(HTTPError):
    """
    Raised when a 502 Bad Gateway error is returned from the API.
    """


# TODO: Add a lock for iteration
def checkCache() -> None:
    """
    Checks the cache to see if any requests have expired.
    """
    global cacheLastChecked

    # Check if the cache needs to be checked
    if time() - cacheLastChecked < 60:
        return

    with cacheLock:
        # Check the cache
        for rhash in cache:
            if cache[rhash]["expires"] >= time():  # If the cache has not expired, skip it
                continue

            del cache[rhash]


class Requester:
    """
    Handles making requests to the RAWG API.
    """
    __sockets__ = ("config", "logger")

    def __init__(
            self,
            config: Config
    ) -> None:
        """
        Initializes the Requester object.

        Args:
            config (Config): The configuration object.
        """
        self.config = config
        self.logger = createLogger("Requester", level=config.logging.level, config=config, includeRequest=False)

    def get(
            self,
            url: str,
            params: Optional[dict[str, Any]] = None,
            headers: Optional[dict[str, str]] = None,
            overwriteUrl: bool = False,
            **kwargs
    ) -> Any:
        """
        Makes a GET request to the RAWG API.

        Args:
            url (str): The URL to make the request to.
            params (Optional[dict[str, Any]]): The parameters to pass to the request.
            headers (Optional[dict[str, str]]): The headers to pass to the request.
            overwriteUrl (bool): Whether to overwrite the whole url or not.
            **kwargs: Any additional keyword arguments to pass to the request.

        Returns:
            Any: The response from the RAWG API.
        """
        return self._action(
            method=get,
            url=url,
            params=params,
            overwriteUrl=overwriteUrl,
            headers=headers,
            **kwargs
        )

    def post(
            self,
            url: str,
            data: Optional[dict[str, Any]] = None,
            headers: Optional[dict[str, str]] = None,
            overwriteUrl: bool = False,
            **kwargs
    ) -> Any:
        """
        Makes a POST request to the RAWG API.

        Args:
            url (str): The URL to make the request to.
            data (Optional[dict[str, Any]]): The data to pass to the request.
            headers (Optional[dict[str, str]]): The headers to pass to the request.
            overwriteUrl (bool): Whether to overwrite the whole url or not.
            **kwargs: Any additional keyword arguments to pass to the request.

        Returns:
            Any: The response from the RAWG API.
        """
        return self._action(
            method=post,
            url=url,
            overwriteUrl=overwriteUrl,
            headers=headers,
            data=data,
            **kwargs
        )

    def put(
            self,
            url: str,
            data: Optional[dict[str, Any]] = None,
            headers: Optional[dict[str, str]] = None,
            overwriteUrl: bool = False,
            **kwargs
    ) -> Any:
        """
        Makes a PUT request to the RAWG API.

        Args:
            url (str): The URL to make the request to.
            data (Optional[dict[str, Any]]): The data to pass to the request.
            headers (Optional[dict[str, str]]): The headers to pass to the request.
            overwriteUrl (bool): Whether to overwrite the whole url or not.
            **kwargs: Any additional keyword arguments to pass to the request.

        Returns:
            Any: The response from the RAWG API.
        """
        return self._action(
            method=put,
            url=url,
            overwriteUrl=overwriteUrl,
            headers=headers,
            data=data,
            **kwargs
        )

    def delete(
            self,
            url: str,
            data: Optional[dict[str, Any]] = None,
            headers: Optional[dict[str, str]] = None,
            overwriteUrl: bool = False,
            **kwargs
    ) -> Any:
        """
        Makes a DELETE request to the RAWG API.

        Args:
            url (str): The URL to make the request to.
            data (Optional[dict[str, Any]]): The data to pass to the request.
            headers (Optional[dict[str, str]]): The headers to pass to the request.
            overwriteUrl (bool): Whether to overwrite the whole url or not.
            **kwargs: Any additional keyword arguments to pass to the request.

        Returns:
            Any: The response from the RAWG API.
        """
        return self._action(
            method=delete,
            url=url,
            params=data,
            overwriteUrl=overwriteUrl,
            headers=headers,
            **kwargs
        )

    def _action(
            self,
            method: Callable,
            url: str,
            params: Optional[dict[str, Any]] = None,
            overwriteUrl: bool = False,
            headers: dict[str, Any] = None,
            skipCache: bool = False,
            **kwargs
    ) -> Any:
        """
        Makes a request to the RAWG API. This is a template method.

        Args:
            method (Callable): The requests function to use.
            url (str): The URL to make the request to.
            params (Optional[dict[str, Any]]): The parameters to pass to the request.
            overwriteUrl (bool): Whether to use only use the URL or include the base URL.
            headers (dict[str, Any]): Headers to pass to the request.
            skipCache (bool): Whether to skip the cache or not.
            **kwargs: Any additional keyword arguments to pass to the request.

        Returns:
            Any: The response from the RAWG API.
        """
        # Create a unique ID for the request
        requestId: str = str(uuid4())

        # Set the URL
        url: str = f"{self.config.api.base}{"/" if not url.startswith("/") and not self.config.api.base.endswith("/") else ""}{url}" if not overwriteUrl else url

        # Yes this does have request context
        self.logger.info(
            f"{requestId} - {method.__name__.upper()} request to {url} with params {params} and kwargs {kwargs}"
        )

        # Check the cache
        checkCache()

        # Calculate request hash
        rHash: str = sha512(f"{url}{params}{headers}{kwargs}".encode()).hexdigest()

        with cacheLock:
            if rHash in cache and not skipCache:
                self.logger.debug(f"{requestId} - Cache hit")
                # Return the data from the cache without the expires key
                _tempCache: dict = cache[rHash].copy()
                _tempCache.pop("expires")
                return _tempCache

        # Add the API key to the data
        if params is None:
            params = {}

        params["key"] = self.config.api.key

        # Set the user agent
        if headers is None:
            headers = {}

        # Add the user agent header
        headers["User-Agent"] = f"AHSHS IA3 {self.config.server.owner.name}"
        headers["From"] = self.config.server.owner.email

        response: Response = method(
            url,
            params=params,
            **kwargs
        )

        # Response is not nullable
        assert response is not None

        self.logger.debug(f"{requestId} - Cache miss")

        # Get the response data
        data: dict = response.json()

        # Edit the data to remove the API key from the next and previous URLs
        if "next" in data and data["next"] is not None:
            data["next"] = data["next"].replace(self.config.api.key, "KEY")

        if "previous" in data and data["previous"] is not None:
            data["previous"] = data["previous"].replace(self.config.api.key, "KEY")

        with cacheLock:
            # Add the data to the cache
            cache[rHash] = data.copy()

            # Add the expiration time to the cache (current time + config.api.cacheExpiry)
            cache[rHash]["expires"] = time() + self.config.api.cacheExpiry

        # Return the data
        return data
