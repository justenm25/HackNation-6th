class GenomeFirewallError(Exception):
    """Base error for expected backend failures."""


class SchemaMismatchError(GenomeFirewallError):
    """Input features do not match the frozen model schema."""


class LeakageError(GenomeFirewallError):
    """A genetic group crosses protected dataset partitions."""


class InputValidationError(GenomeFirewallError):
    """An input is malformed or incompatible."""

