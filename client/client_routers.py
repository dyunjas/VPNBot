from aiogram import Router

from client.navigation.main_menu import main_menu
from client.navigation.additional_menu.information import information
from client.navigation.additional_menu.profile import profile
from client.navigation.additional_menu.profile import promocode
from client.navigation.subscription import subscription
from client.navigation.purchase import purchase
from client.vpn_key import create_vpn_key
from client.vpn_key import show_vpn_key
from client.vpn_key import delete_vpn_key
from client.payments import add_funds, platega_payment
from client.navigation.additional_menu.transaction import transaction
from client.navigation.additional_menu.email import email
from client.navigation.additional_menu.referral import referral

router = Router()

router.include_router(main_menu.router)
router.include_router(information.router)
router.include_router(profile.router)
router.include_router(subscription.router)
router.include_router(purchase.router)
router.include_router(create_vpn_key.router)
router.include_router(show_vpn_key.router)
router.include_router(delete_vpn_key.router)
router.include_router(promocode.router)
router.include_router(add_funds.router)
router.include_router(platega_payment.router)
router.include_router(transaction.router)
router.include_router(email.router)
router.include_router(referral.router)