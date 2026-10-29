"""Exception types raised by ctfw."""


class CtfwError(Exception):
    """An expected, user-facing error (bad input, missing file, ...).

    The CLI prints the message and exits with status 2 instead of showing a
    traceback.
    """
