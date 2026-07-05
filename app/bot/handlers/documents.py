"""/mydocs: upload/replace/delete resume, cover letters, notes."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.docparse import parse_document
from app.bot.keyboards import kb
from app.bot.states import DocUpload
from app.db.models import Document, User
from app.i18n import t

router = Router()

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_DOCS = 10


async def _docs_menu(message: Message, session: AsyncSession, user: User, edit: bool = False):
    docs = (await session.execute(
        select(Document).where(Document.user_tg_id == user.tg_id)
        .order_by(Document.created_at.desc())
    )).scalars().all()
    lang = user.language
    rows: list[list[tuple[str, str]]] = []
    lines = [t("menu_docs_title", lang, count=len(docs))]
    if not docs:
        lines.append(t("docs_empty", lang))
    for doc in docs:
        icon = "📄" if doc.doc_type == "resume" else "📝"
        lines.append(f"{icon} {doc.filename} ({len(doc.extracted_text)} chars)")
        rows.append([(f"{t('btn_delete', lang)} {doc.filename[:25]}", f"deldoc:{doc.id}")])
    rows.append([(t("btn_upload_resume", lang), "updoc:resume")])
    rows.append([(t("btn_upload_cover", lang), "updoc:cover")])
    text = "\n".join(lines)
    if edit:
        await message.edit_text(text, reply_markup=kb(rows))
    else:
        await message.answer(text, reply_markup=kb(rows))


@router.message(Command("mydocs"))
async def cmd_mydocs(message: Message, session: AsyncSession, user: User):
    await _docs_menu(message, session, user)


@router.callback_query(F.data.startswith("updoc:"))
async def cb_upload(query: CallbackQuery, user: User, state: FSMContext):
    kind = query.data.split(":")[1]
    await query.answer()
    if kind == "resume":
        await query.message.answer(t("upload_prompt_resume", user.language))
        await state.set_state(DocUpload.waiting_resume)
    else:
        await query.message.answer(t("upload_prompt_cover", user.language))
        await state.set_state(DocUpload.waiting_cover)


@router.callback_query(F.data.startswith("deldoc:"))
async def cb_delete(query: CallbackQuery, session: AsyncSession, user: User):
    doc = await session.get(Document, int(query.data.split(":")[1]))
    if doc is not None and doc.user_tg_id == user.tg_id:
        await session.delete(doc)
        await session.flush()
    await query.answer(t("doc_deleted", user.language))
    await _docs_menu(query.message, session, user, edit=True)


async def _save_document(message: Message, session: AsyncSession, user: User,
                         doc_type: str, state: FSMContext) -> None:
    lang = user.language
    if message.document is not None:
        if (message.document.file_size or 0) > MAX_FILE_BYTES:
            await message.answer(t("doc_too_big", lang))
            return
        file = await message.bot.get_file(message.document.file_id)
        buffer = await message.bot.download_file(file.file_path)
        filename = message.document.file_name or "document"
        try:
            text = await parse_document(buffer.read(), filename)
        except ValueError:
            await message.answer(t("doc_parse_failed", lang))
            return
    elif message.text and doc_type != "resume":
        filename = f"note_{message.message_id}.txt"
        text = message.text[:30000]
    else:
        await message.answer(t("doc_parse_failed", lang))
        return

    if doc_type == "resume":
        # replace: only one active resume at a time
        old = (await session.execute(
            select(Document).where(Document.user_tg_id == user.tg_id,
                                   Document.doc_type == "resume")
        )).scalars().all()
        for o in old:
            await session.delete(o)
    else:
        count = len((await session.execute(
            select(Document.id).where(Document.user_tg_id == user.tg_id)
        )).scalars().all())
        if count >= MAX_DOCS:
            await message.answer(t("doc_too_big", lang))
            return

    session.add(Document(user_tg_id=user.tg_id, doc_type=doc_type,
                         filename=filename, extracted_text=text))
    await session.flush()
    await state.clear()
    await message.answer(t("doc_saved", lang, name=filename, chars=len(text)))


@router.message(DocUpload.waiting_resume)
async def msg_resume(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await _save_document(message, session, user, "resume", state)


@router.message(DocUpload.waiting_cover)
async def msg_cover(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await _save_document(message, session, user, "cover", state)
