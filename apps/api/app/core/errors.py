class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str, *, details=None,
                 current_version=None, retryable=False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.current_version = current_version
        self.retryable = retryable

    def body(self):
        return {"error": {"code": self.code, "message": self.message,
                "retryable": self.retryable, "current_version": self.current_version,
                "details": self.details}}


def not_found():
    return DomainError(404, "RESOURCE_NOT_FOUND", "대상을 찾을 수 없습니다.")
