from tkinter import messagebox
import logging
from typing import Callable

def show_warning(message: str, title: str = "Warning") -> None:
    """Show waring dialog box with one OK button.

    Args:
        message (str): Message shown in the body of the dialog box.
        title (str, optional): Title of the dialog box.. Defaults to "Warning".
        
    Warnings are for when an action can not be performed currently
    but the issue can be resolved within the application.

    For more serious issues use errors.
    """
    log = logging.getLogger("root")
    log.info(f"Warning shown: {title} | {message}")
    messagebox.showwarning(title, message)


def show_info(message: str, title: str = "Info") -> None:
    """Show info dialog box with one OK button.

    Args:
        message (str): Message shown in the body of the dialog box.
        title (str, optional): Title of the dialog box.. Defaults to "Info".
    """
    log = logging.getLogger("root")
    log.info(f"Info shown: {title} | {message}")
    messagebox.showinfo(title, message)


def ask_non_fatal_error(message: str, title: str = "Error") -> bool:
    """Show error dialog box with one RETRY and one CANCEL button.

    Args:
        message (str): Message shown in the body of the dialog box.
        title (str, optional): Title of the dialog box. Defaults to "Error".

    Returns:
        bool: True if the user wants to retry, False otherwise.
        
    Non-fatal errors are for when an action can not be performed currently
    and can not be resolved entirely within the application,
    but can be resumed and successfully completed from the current state
    after changing some settings on the user's machine.

    Non-fatal errors can be dismissed.
    """
    log = logging.getLogger("root")
    log.info(f"Non-fatal error shown: {title} | {message}")
    return messagebox.askretrycancel(title, message)


def ask_aborting_error(abort_command: Callable, message: str, title: str = "Fatal error") -> None:
    """Show error dialog box with one RETRY and one CANCEL button.

    Args:
        abort_command (Callable): Command to call if user decides to abort.
        message (str): Message shown in the body of the dialog box.
        title (str, optional): Title of the dialog box. Defaults to "Fatal error".
        
    The user can decide to retry and continue exporting or abort it.
    
    Aborting errors are for when an action cannot be performed
    that is an integral part of the exporting process.
    Aborting errors do not threaten exiting the program,
    only aborting the exporting process.
    """    
    log = logging.getLogger("root")
    message += "\n\nRetry or exporting will be aborted."
    log.info(f"Aborting error shown: {title} | {message}")
    if not messagebox.askretrycancel(title, message):
        log.info(f"Abort initiated from aborting error: {title} | {message}")
        abort_command()


def ask_fatal_error(message: str, title: str = "Fatal error") -> bool:
    """Show fatal error dialog box with one RETRY and one CANCEL button.

    Args:
        message (str): Message shown in the body of the dialog box.
        title (str, optional): Title of the dialog box. Defaults to "Fatal error".

    Returns:
        bool: True if the user wants to retry, False indicating that the program should exit.

    Fatal errors are for when an action cannot be performed
    which is an essential part of the program.
    Fatal errors lead to termination that should be initiated by the caller.
    """
    log = logging.getLogger("root")
    message += "\n\nRetry or the program will exit automatically."
    log.info(f"Fatal error shown: {title} | {message}")
    return messagebox.askretrycancel(title, message)
