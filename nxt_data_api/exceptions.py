class NXTError(Exception):
    pass


class NXTFetchError(NXTError):
    pass


class UnknownEndpointError(NXTError):
    pass
