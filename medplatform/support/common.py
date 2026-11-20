from ..core.errors import AppError

CONTRACT = "C-v0.2"


def missing():
    return AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
