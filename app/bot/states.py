"""FSM state groups for multi-step conversations."""
from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    language = State()
    degree = State()
    fields = State()
    english_test = State()
    english_score = State()
    english_expiry = State()
    gpa = State()


class DocUpload(StatesGroup):
    waiting_resume = State()
    waiting_cover = State()


class SearchFlow(StatesGroup):
    naming_filter = State()


class AdminEdit(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
