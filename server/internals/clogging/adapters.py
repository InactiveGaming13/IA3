"""
Adapters module for custom logging system.
"""

# Standard Library Imports
from logging import Logger, LoggerAdapter

# Third Party Imports

# Local Imports

# Constants

# Custom LoggerAdapter that can be disabled
class SuppressedLoggerAdapter(LoggerAdapter):
    """
    A logger adapter that can be disabled.
    """
    # Type hints
    suppressed: bool

    def __init__(
            self,
            logger: Logger,
            extra: dict[str, str] | None = None
    ) -> None:
        super().__init__(logger, extra)
        self.suppressed = False

    def __del__(self) -> None:
        """
        This method is called when the object is deleted.

        Returns:
            None
        """
        del self

    def suppress(self) -> None:
        """
        Suppresses the logger.
        """
        self.suppressed = True

    def unsuppress(self) -> None:
        """
        Unsuppresses the logger.
        """
        self.suppressed = False

    def log(
            self,
            level: int,
            msg: str,
            *args,
            **kwargs
    ) -> None:
        """
        Logs the message to the logger.

        Args:
            level (int): The level of the log message.
            msg (str): The log message.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.
        """
        # This does have request context
        if not self.suppressed:
            super().log(level, msg, *args, **kwargs)
