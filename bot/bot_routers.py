from aiogram import Router

from bot.navigation.main_menu import main_menu
from bot.navigation.additional_menu.information import information
from bot.navigation.additional_menu.profile import profile
from bot.navigation.additional_menu.profile import promocode
from bot.navigation.subscription import subscription
from bot.navigation.purchase import purchase
from bot.payments import add_funds, platega_payment
from bot.navigation.additional_menu.transaction import transaction
from bot.navigation.additional_menu.referral import referral
from bot.vpn_subscription import subscription_url
from bot.vpn_subscription.reissue_keys import reissue_keys
from bot.payments import cryptobot_payment

router = Router()

router.include_router(main_menu.router)
router.include_router(information.router)
router.include_router(profile.router)
router.include_router(subscription.router)
router.include_router(purchase.router)
router.include_router(promocode.router)
router.include_router(add_funds.router)
router.include_router(platega_payment.router)
router.include_router(cryptobot_payment.router)
router.include_router(transaction.router)
router.include_router(referral.router)
router.include_router(subscription_url.router)
router.include_router(reissue_keys.router)