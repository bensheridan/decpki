class DecPKIError(Exception):
    pass


class QuorumError(DecPKIError):
    def __init__(self, required: int, provided: int):
        self.required = required
        self.provided = provided
        super().__init__(
            f"Quorum not met: need {required} validator(s), got {provided}"
        )


class DuplicateDIDError(DecPKIError):
    def __init__(self, did: str):
        self.did = did
        super().__init__(f"DID already registered: {did}")


class BundleDecodeError(DecPKIError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Bundle decode failed: {reason}")
