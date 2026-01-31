class ServiceError(Exception):
    pass

class UserNotFound(ServiceError):
    pass

class SubscriptionNotFound(ServiceError):
    pass

class PlanNotFound(ServiceError):
    pass

class InsufficientBalance(ServiceError):
    pass


class TransactionNotFound(ServiceError):
    pass

class PaymentNotConfirmed(ServiceError):
    pass


class KeyCreationError(ServiceError):
    pass

class TrafficError(ServiceError):
    pass

class PromocodeNotFound(ServiceError):
    pass


class PromocodeAlreadyUsed(ServiceError):
    pass

class PromocodeExpired(ServiceError):
    pass

class PromocodeExhausted(ServiceError):
    pass

class ServerNotFound(ServiceError):
    pass

class EmailNotFound(ServiceError):
    pass

class EmailVerificationNotFound(ServiceError):
    pass

class EmailVerificationExpired(ServiceError):
    pass

class InvalidVerificationCode(Exception):
    pass

class TooManyAttempts(Exception):
    pass
