class LawsError(Exception):
    """Base class for errors reported back to the model as text."""


class GitError(LawsError):
    pass


class ResolveError(LawsError):
    pass


class NotReadyError(LawsError):
    pass
