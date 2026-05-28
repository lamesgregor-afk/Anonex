from aiogram import Router
from .start import router as start_router
from .listings import router as listings_router
from .orders import router as orders_router
from .wallet import router as wallet_router
from .admin import router as admin_router
from .reviews import router as reviews_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(listings_router)
main_router.include_router(orders_router)
main_router.include_router(wallet_router)
main_router.include_router(admin_router)
main_router.include_router(reviews_router)

__all__ = ["main_router"]
