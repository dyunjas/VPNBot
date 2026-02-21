class ServiceError(Exception):
    pass

class UserNotFound(ServiceError):
    pass

class SubscriptionNotFound(ServiceError):
    pass

class PlanNotFound(ServiceError):
    pass

class TooEarlyToRenew(Exception):
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


class WithdrawalNotFound(Exception):
    pass


class WithdrawalNotPending(Exception):
    pass


class NotEnoughReferralBalance(Exception):
    pass

class AdminPermissionDenied(Exception):
    pass


class DeviceLimitReached(Exception):
    pass

class DeviceNotFound(Exception):
    pass

