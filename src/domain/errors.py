class WpdError(Exception):
    pass


class ScanError(Exception):
    def __init__(self, message_key: str, detail: str | None = None) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.detail = detail


class ScanCancelled(Exception):
    pass


class TransferError(Exception):
    def __init__(self, message_key: str, detail: str | None = None) -> None:
        super().__init__(message_key)
        self.message_key = message_key
        self.detail = detail


class ConversionError(Exception):
    pass
