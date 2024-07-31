"""
Handlers for the logging system.
"""

# Standard Library Imports
from asyncio import create_task
from datetime import datetime
from logging import Handler, LogRecord
from os import getcwd
from pathlib import Path

# External Imports
from flask import Response, g, has_request_context, request
from psycopg2 import connect as pgConnect
from psycopg2.extras import Json, RealDictConnection, RealDictCursor

# Local Imports
from ..config import Config


class DatabaseLogHandler(Handler):
    """
    A handler that logs all information to a sqlite database and periodically removes logs older than one week.
    """
    __slots__ = ("file", "connection", "includeRequest")

    def __init__(
            self,
            config: Config
    ) -> None:
        """
        Initializes the handler.

        Args:
            config (Config): The config object to use.
        """
        super().__init__()
        self.connection: RealDictConnection = pgConnect(
            dbname=config.logging.db.name,
            user=config.logging.db.username,
            password=config.logging.db.password,
            host=config.logging.db.host,
            port=config.logging.db.port,
            connection_factory=RealDictConnection
        )

        # Set includeRequest to False by default
        self.includeRequest: bool = False

    def __del__(self):
        """
        This method is called when the object is deleted.

        Returns:
            None
        """
        self.connection.close()
        del self

    def _createSchema(self) -> None:
        """
        Creates the schema for the database.

        Returns:
            None
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Read the schema file
            with open(Path(f"{getcwd()}/internals/logging/schema.sql"), "r") as schemaFile:
                schema: str = schemaFile.read()

            # Execute the schema
            cursor.executemany(schema, None)

        self.connection.commit()

    def emit(
            self,
            record: LogRecord
    ) -> None:
        """
        Emits the log record to the sqlite database.

        Planning:
            Theoretically, this should have access to the request object, so it can log the request information.

        Args:
            record (LogRecord): The log record to emit.

        Returns:
            None
        """

        # Create a cursor for the whole function
        cursor: RealDictCursor = self.connection.cursor(cursor_factory=RealDictCursor)

        # Add the record to the database and get the id
        recordId: str = self._logRecord(cursor, record)  # Why is this not being executed when request context is present

        if not has_request_context() or not self.includeRequest:
            return

        # Check what state the request is in
        if not g.completed:
            self._logRequest(cursor, recordId)

        else:
            self._logResponse(cursor, g.response)

        self.connection.commit()

    @staticmethod
    def _logRecord(
            cursor: RealDictCursor,
            record: LogRecord
    ) -> str:
        """
        Logs the record to the database.

        Args:
            cursor (RealDictCursor): The cursor to use.
            record (LogRecord): The record to log.

        Returns:
            str: The id of the record.
        """

        cursor.execute(
            """
            INSERT INTO ia3.program_logs (
                timestamp,
                level,
                filename,
                funcname,
                lineno,
                message,
                module,
                name,
                pathname,
                process,
                process_name,
                thread,
                thread_name
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id;
            """,
            (
                datetime.fromtimestamp(record.created),
                record.levelno,
                record.filename,
                record.funcName,
                record.lineno,
                record.msg,
                record.module,
                record.name,
                record.pathname,
                record.process,
                record.processName,
                record.thread,
                record.threadName
            )
        )

        return cursor.fetchone()["id"]

    @staticmethod
    def _logRequest(
            cursor: RealDictCursor,
            recordId: str
    ) -> None:
        """
        Logs the request information to the database.

        Args:
            cursor (RealDictCursor): The cursor to use.
            recordId (str): The id of the record.

        Returns:
            None
        """
        # Check if the X-Forwarded-For header is present
        if "X-Forwarded-For" in request.headers:
            remoteAddr = request.headers["X-Forwarded-For"]
        else:
            remoteAddr = request.remote_addr

        DatabaseLogHandler._execute(
            cursor,
            """
            INSERT INTO ia3.requests (
                id, 
                log_id, 
                view_args, 
                routing_exception, 
                endpoint, 
                blueprint, 
                blueprints,
                accept_languages, 
                accept_mimetypes, 
                access_route, 
                args, 
                "authorization", 
                base_url, 
                cookies, 
                full_path, 
                host, 
                host_url, 
                url, 
                method, 
                headers, 
                remote_addr
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                str(g.uuid),
                recordId,
                Json(request.view_args) if request.view_args is not None else None,
                request.routing_exception.__str__() if request.routing_exception is not None else None,
                request.endpoint if request.endpoint is not None else None,
                request.blueprint if request.blueprint is not None else None,
                request.blueprints if request.blueprints is not None else None,
                request.accept_languages.__str__() if request.accept_languages is not None else None,
                request.accept_mimetypes.__str__() if request.accept_mimetypes is not None else None,
                request.access_route if request.access_route is not None else None,
                Json(request.args.to_dict()) if request.args is not None else None,
                request.authorization.__str__() if request.authorization is not None else None,
                request.base_url if request.base_url is not None else None,
                Json(request.cookies.to_dict()) if request.cookies is not None else None,
                request.full_path if request.full_path is not None else None,
                request.host if request.host is not None else None,
                request.host_url if request.host_url is not None else None,
                request.url if request.url is not None else None,
                request.method if request.method is not None else None,
                request.headers.__str__() if request.headers is not None else None,
                remoteAddr  # This will never be None
            )
        )

    @staticmethod
    def _logResponse(
            cursor: RealDictCursor,
            response: Response
    ) -> None:
        """
        Logs the response information to the database.

        Args:
            cursor (RealDictCursor): The cursor to use.
            response (Response): The response object to log.

        Returns:
            None
        """
        DatabaseLogHandler._execute(
            cursor,
            """
            INSERT INTO ia3.responses (
                request_id, 
                expires, 
                location, 
                status, 
                status_code, 
                headers, 
                response
            ) VALUES  (
                %s, %s, %s, %s, %s, %s, %s
            );
            """,
            (
                str(g.uuid),
                response.expires if response.expires is not None else None,
                response.location if response.location is not None else None,
                response.status if response.status is not None else None,
                response.status_code if response.status_code is not None else None,
                response.headers.__str__() if response.headers is not None else None,
                response.response.__str__() if response.response is not None else None
            )
        )

    @staticmethod
    def _execute(
            cursor: RealDictCursor,
            query: str,
            *args
    ) -> None:
        """
        Executes a query on the cursor.

        Args:
            cursor (RealDictCursor): The cursor to use.
            query (str): The query to execute.
            *args: The arguments to pass to the query.

        Returns:
            None
        """
        cursor.execute(query, args)
