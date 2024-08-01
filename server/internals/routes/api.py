"""
Contains apiBlueprint routes. Has urlPrefix of /api. Soley for forwarding requests to RAWG without exposing the API key.
"""
from typing import Dict

# Third Party Imports
from flask import request
from flask.blueprints import Blueprint
from flask_injector import inject

# Internal Imports
from ..wrapper import API

# Standard Library Imports

apiBlueprint: Blueprint = Blueprint("api", __name__, url_prefix="/api")


# Create one route that consumes the url and forwards it to the RAWG API
@apiBlueprint.get("/<path:url>", strict_slashes=False)
@inject
def index(
        url: str,
        api: API
) -> Dict:
    """
    The API forwarding route. Requests have to come from the server itself.

    Args:
        url (str): The URL to forward to the RAWG API.
        api (API): The API wrapper to use (injected).

    Returns:
        str: The response from the RAWG API.
    """
    # if request.remote_addr != config.server.host and config.server.debug is False:  # This was an oversight. It does not work
    #     raise Unauthorized("Requests to the API must come from the server itself.")

    # Get the data
    print(api.requester.get(url, request.args.to_dict()))
    return api.requester.get(url, request.args.to_dict())
