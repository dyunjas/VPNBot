from aiogram.fsm.state import StatesGroup, State

class PromocodeStates(StatesGroup):
    waiting_for_code = State()

class PaymentStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_system = State()

class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media_choice = State()
    waiting_for_photo = State()
    waiting_for_confirmation = State()

class WithdrawBalance(StatesGroup):
    waiting_for_amount = State()
    waiting_for_method = State()
    waiting_for_confirmation = State()


class TransferReferralBalance(StatesGroup):
    waiting_for_amount = State()
    waiting_for_confirmation = State()


class TrafficPurchaseStates(StatesGroup):
    waiting_for_gb = State()
    waiting_for_confirmation = State()


class DeviceSlotsPurchaseStates(StatesGroup):
    waiting_for_slots = State()
    waiting_for_confirmation = State()


class GiftSubscriptionStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_confirmation = State()


class EmailBindStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_code = State()


class CaptchaStates(StatesGroup):
    waiting_for_answer = State()
