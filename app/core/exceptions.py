from fastapi import HTTPException, status


class UserNotFoundException(HTTPException):
    def __init__(self, user_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' was not found."
        )


class PathNotFoundException(HTTPException):
    def __init__(self, start: str, end: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No path found between user '{start}' and user '{end}'."
        )


class ConnectionAlreadyExistsException(HTTPException):
    def __init__(self, user_id_1: str, user_id_2: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A connection between '{user_id_1}' and '{user_id_2}' already exists."
        )
