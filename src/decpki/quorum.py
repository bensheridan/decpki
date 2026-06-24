from .exceptions import DuplicateDIDError, QuorumError
from .models import IdentityLog, IdentityRecord, ValidatorNode


def register_identity(
    log: IdentityLog,
    record: IdentityRecord,
    validators: list[ValidatorNode],
    threshold: int,
) -> IdentityRecord:
    if len(validators) < threshold:
        raise QuorumError(required=threshold, provided=len(validators))

    record.issued_at = log.next_block
    record.issued_by = [v.did for v in validators]

    log.add(record)
    return record
