from aiogram import Router, types

router = Router()

@router.message()
async def process_group(msg: types.Message):
    pass