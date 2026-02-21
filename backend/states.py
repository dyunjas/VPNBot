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
    
class GbAddStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_purchase = State()

class WithdrawBalance(StatesGroup):
    waiting_for_amount = State()
    waiting_for_method = State()
    waiting_for_confirmation = State()