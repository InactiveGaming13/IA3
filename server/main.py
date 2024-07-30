"""
Main file for IA3 Project.
"""

# Standard Library Imports
from datetime import datetime
from logging import getLogger
from os import chdir, getcwd
from typing import List
from uuid import uuid4

# Third Party Imports
from flask import Flask, Response, g, request
from flask_injector import FlaskInjector
from injector import Binder, singleton

# Local Imports
from internals.clogging import SuppressedLoggerAdapter, createLogger
from internals.config import Config
from internals.routes import *
from internals.wrapper.api import API

# Constants
EXPECTED_COOKIES: List[str] = ["theme", "age"]

# Before we do anything, check if the working directory is correct. This is a fix for running the server from parent directory using the start script.
if not getcwd().endswith("server"):
    chdir("server")

# Constants
config: Config = Config()

# Create the logger
logger: SuppressedLoggerAdapter = createLogger(
    "endpoints",
    level=config.logging.level,
    includeRequest=True,
    config=config
)

# Check environment variable debug
if not config.server.debug:
    # Kill the standard werkzeug logger
    werkzeugLogger = getLogger("werkzeug")
    werkzeugLogger.disabled = True

# Connect to the API
api: API = API(config)

# Add a workaround for a bug in FlaskInjector
Flask.url_for.__annotations__ = {}

# Create the Flask app
app: Flask = Flask(__name__, template_folder="templates")

# Set static and template folders
app.static_folder = "static"
app.template_folder = "templates"

# Add routes
app.register_blueprint(infoBlueprint)
app.register_blueprint(gamesBlueprint)
app.register_blueprint(testsBlueprint)
app.register_blueprint(apiBlueprint)
app.register_blueprint(errorsBlueprint)


@app.before_request
def beforeRequest() -> None:
    """
    Runs before each request. Ensures that the user is logged in.

    If the user is not logged in, respond with a 401 error code.

    Returns:
        None
    """
    # Set request uuid
    g.uuid = uuid4()
    g.completed = False
    logger.info(  # 2 spaces here to match the indentation of the response log
        f"Request  [{g.uuid}] [{request.method}] [{request.path}] from {request.headers['X-Forwarded-For'] if 'X-Forwarded-For' in request.headers else request.remote_addr} with "
        f"with cookies {request.cookies.to_dict()}"
    )
    return


@app.context_processor
def processor() -> dict:
    """
    Injects site-wide variables into the template context.
    """
    return {
        "year": datetime.now().year,
        "owner": config.server.owner
    }


@app.after_request
def afterRequest(
        response: Response
) -> Response:
    """
    Runs after each request. Logs the response and deals with cookies.

    Args:
        response (Response): The response to log.

    Returns:
        Response: The response.
    """
    g.completed = True
    g.response = response
    logger.info(f"Response [{g.uuid}] [{response.status_code}]")

    # # Add a theme cookie to the response if the user doesn't have one
    # if "theme" not in request.cookies:
    #     response.set_cookie("theme", config.server.theme, samesite="Strict")

    # Purge any cookies that are not expected
    for cookie in request.cookies:
        if cookie not in EXPECTED_COOKIES:
            response.delete_cookie(cookie)

    return response


def configureDependencies(
        binder: Binder
) -> None:
    """
    Configures the dependencies for the app.

    Args:
        binder (Binder): The binder to use.

    Returns:
        None
    """
    binder.bind(Config, config, scope=singleton)
    binder.bind(API, api, scope=singleton)


# Add dependencies
FlaskInjector(app=app, modules=[configureDependencies])

# Run the app
if __name__ == "__main__":
    # Log the start of the server including what address and port it is running on
    logger.info(f"Server started on following addresses: {f'{"https" if config.server.ssl else "http"}://{config.server.host}:{config.server.port}'}")

    app.run(
        host=config.server.host,
        port=config.server.port,
        debug=config.server.debug
    )
