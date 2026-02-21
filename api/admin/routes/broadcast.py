from fastapi import APIRouter
from ..common import *

router = APIRouter()

@router.post("/broadcast/upload", dependencies=[Depends(require_admin_auth)])
async def admin_broadcast_upload(
    text: str = Form(...),
    parse_mode: Literal["HTML", "MarkdownV2"] = Form("HTML"),
    include_banned: bool = Form(False),
    image: UploadFile | None = File(default=None),
):
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    image_bytes: bytes | None = None
    image_name = "broadcast.jpg"
    if image is not None:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="image is empty")
        image_name = image.filename or image_name

    async with async_session() as session:
        query = select(User)
        if not include_banned:
            query = query.where(User.banned.is_(False))
        users = list((await session.execute(query)).scalars().all())

    success = 0
    failed = 0
    failed_ids: list[int] = []
    for user in users:
        try:
            if image_bytes:
                photo = BufferedInputFile(image_bytes, filename=image_name)
                await bot.send_photo(
                    chat_id=user.tg_id,
                    photo=photo,
                    caption=text,
                    parse_mode=parse_mode,
                )
            else:
                await bot.send_message(
                    chat_id=user.tg_id,
                    text=text,
                    parse_mode=parse_mode,
                )
            success += 1
        except Exception:
            failed += 1
            if len(failed_ids) < 30:
                failed_ids.append(int(user.tg_id))
        finally:
            await asyncio.sleep(0.05)

    return {
        "ok": True,
        "total": len(users),
        "success": success,
        "failed": failed,
        "failed_tg_ids": failed_ids,
        "premium_emoji_note": "Use HTML with <tg-emoji emoji-id='...'> and parse_mode=HTML",
    }


