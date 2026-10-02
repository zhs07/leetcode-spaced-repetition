"""Storage failures independent of a particular database driver."""


class StorageError(RuntimeError):
    pass


class DuplicateProblem(StorageError):
    pass


class ProblemNotFound(StorageError):
    pass
