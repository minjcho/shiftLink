class ActionError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 *, current_version: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.current_version = current_version
        self.details = details or {}

    def envelope(self, meta: dict) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "retryable": self.code == "COMMAND_IN_PROGRESS",
                          "current_version": self.current_version,
                          "details": self.details}, "meta": meta}
