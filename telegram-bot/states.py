from aiogram.fsm.state import State, StatesGroup


class RegisterStation(StatesGroup):
    code = State()
    existing_offer = State()
    city = State()
    district = State()
    operational_area = State()
    address = State()
    name = State()
    gps = State()
    confirm = State()


class UpdateStation(StatesGroup):
    code = State()
    menu = State()
    city = State()
    district = State()
    text_value = State()
    gps = State()
    confirm = State()


class SearchStation(StatesGroup):
    query = State()
