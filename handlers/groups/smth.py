from aiogram import Router, types, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from datetime import datetime
import re

router = Router()

EMOJI_PATTERN = re.compile(
    r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF'
    r'\U0001F1E0-\U0001F1FF\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF\u200D\uFE0F\u20E3'
    r'\U0001F1F2-\U0001F1F4\U0001F1E6-\U0001F1FF]+$'
)

EDIT_PATTERN = re.compile(r'^#USER_(\d+)$')


def is_single_emoji(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if not text:
        return False
    return bool(EMOJI_PATTERN.match(text))


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get_reply_post(chat_id: int, reply_msg_id: int):
    """Try to find the post by to_message_id (bot copy) first, then by original message_id."""
    post = db.select_post(to_message_id=reply_msg_id)
    if not post:
        post = db.select_post(to_id=chat_id, message_id=reply_msg_id)
    return post


def _get_reply_user(reply_post):
    """Get anon_name of user who wrote the reply target."""
    if not reply_post:
        return None
    reply_up = db.select_user_post(post=reply_post[0])
    if reply_up:
        reply_user = db.select_user(id=reply_up[1])
        if reply_user:
            return reply_user[2]
    return None


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    if message.from_user.is_bot:
        return
    chat_id = message.chat.id
    user = message.from_user

    db_user = db.get_or_create_user(
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    anon_name = db_user[2]
    content = message.text or message.caption or ""

    if is_single_emoji(content) and message.reply_to_message:
        post = _get_reply_post(chat_id, message.reply_to_message.message_id)
        if post:
            db.add_reaction(message.from_user.id, post[0], content)
            org = message.reply_to_message.text or message.reply_to_message.caption or ""
            org += "\n<quote>REACTIONS: "
            await bot.edit_message_caption(chat_id=chat_id, message_id=post[2], caption="")
            await bot.edit_message_text(text="",chat_id=chat_id, message_id=post[2])


    # --- Edit-by-reference: "#5 new text" ---
    edit_match = EDIT_PATTERN.match(content)
    if edit_match:
        target_post_id = int(edit_match.group(1))
        new_text = edit_match.group(2)
        post = db.select_post(id=target_post_id)
        if post:
            up = db.select_user_post(post=target_post_id)
            if up and up[1] == db_user[0]:
                escaped = _esc(new_text)
                lines = [f"<b>{anon_name} (edited)</b>", escaped]
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=post[3],
                        text="\n".join(lines), parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.info(f"Edit failed: {e}")
        await message.delete()
        return

    # --- Single emoji = REACTION ---
    if is_single_emoji(content):
        target_post = None
        if message.reply_to_message:
            target_post = _get_reply_post(chat_id, message.reply_to_message)
        else:
            target_post = db.select_last_post(to_id=chat_id)

        if not target_post:
            return

        target_post_id = target_post[0]
        now_ts = int(datetime.now().timestamp())
        db.add_reaction(
            user=db_user[0], post=target_post_id,
            reaction=content.strip(), created_at=now_ts
        )
        await message.delete()
        return

    # --- Normal message ---
    lines = [f"<quote>{anon_name}</quote>"]

    reply_post = None
    if message.reply_to_message:
        reply_post = _get_reply_post(chat_id, message.reply_to_message)
        reply_user = _get_reply_user(reply_post)
        if reply_user:
            lines.append(f"<quote>#REPLY_TO #{reply_user}</quote>")
            lines.append(f"#REPLY_TO_MESSAGE #MESSAGE_{reply_post[0]}")
    lines.append(f"#MESSAGE_{message.message_id}")

    if content:
        escaped = _esc(content)
        lines.append('\n')
        lines.append(escaped)

    # Send message to group
    if message.photo:
        sent = await bot.send_photo(
            chat_id=chat_id, photo=message.photo[-1].file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    elif message.video:
        sent = await bot.send_video(
            chat_id=chat_id, video=message.video.file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    elif message.animation:
        sent = await bot.send_animation(
            chat_id=chat_id, animation=message.animation.file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    else:
        sent = await bot.send_message(
            chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML
        )

    # Save to DB
    db.add_post(
        to_id=chat_id, message_id=message.message_id,
        to_message_id=sent.message_id, channel_id=chat_id,
        created_at=datetime.now()
    )
    last_post = db.select_post(to_id=chat_id, message_id=message.message_id)
    if last_post:
        db.add_user_post(user=db_user[0], post=last_post[0])
        # post_id = last_post[0]
        # Update message with post numbers
        # number_line = f"\n#{post_id}"
        # if reply_post:
        #     number_line += f"  reply to #{reply_post[0]}"

        # updated_lines = lines + [number_line]
        # try:
        #     if message.photo or message.video or message.animation:
        #         await bot.edit_message_caption(
        #             chat_id=chat_id, message_id=sent.message_id,
        #             caption="\n".join(updated_lines), parse_mode=ParseMode.HTML
        #         )
        #     else:
        #         await bot.edit_message_text(
        #             chat_id=chat_id, message_id=sent.message_id,
        #             text="\n".join(updated_lines), parse_mode=ParseMode.HTML
        #         )
        # except Exception as e:
        #     logger.info(f"Post number update failed: {e}")

    await message.delete()
