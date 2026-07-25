from aiogram import Router

from bot.navigation.main_menu import main_menu
from bot.navigation.additional_menu.information import information
from bot.navigation.additional_menu.email import email
from bot.navigation.additional_menu.balance import balance, promocode
from bot.navigation.subscription import subscription
from bot.navigation.purchase import purchase
from bot.payments import add_funds, platega_payment, pally_payment
from bot.navigation.additional_menu.transaction import transaction
from bot.navigation.additional_menu.referral import referral
from bot.navigation.additional_menu.referral import withdraw_balance
from bot.vpn_subscription import subscription_url
from bot.vpn_subscription import devices
from bot.vpn_subscription import traffic_purchase
from bot.payments import cryptobot_payment, stars_topup

router = Router()

router.include_router(main_menu.router)
router.include_router(information.router)
router.include_router(email.router)
router.include_router(balance.router)
router.include_router(subscription.router)
router.include_router(purchase.router)
router.include_router(promocode.router)
router.include_router(add_funds.router)
router.include_router(platega_payment.router)
router.include_router(pally_payment.router)
router.include_router(cryptobot_payment.router)
router.include_router(stars_topup.router)
router.include_router(transaction.router)
router.include_router(referral.router)
router.include_router(withdraw_balance.router)
router.include_router(subscription_url.router)
router.include_router(devices.router)
router.include_router(traffic_purchase.router)
