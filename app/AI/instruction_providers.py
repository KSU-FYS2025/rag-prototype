from google.adk.agents.readonly_context import ReadonlyContext
from collections.abc import Callable


def get_from_file_path(file_path: str) -> Callable[[ReadonlyContext], str]:
    def get_from_file(context: ReadonlyContext) -> str:
        with open(file_path, "r") as file:
            return file.read()

    return get_from_file
