from aiogram.fsm.state import State, StatesGroup


class AddStation(StatesGroup):
    code = State()
    existing_action = State()
    city = State()
    district = State()
    operational_area = State()
    address = State()
    name_choice = State()
    name = State()
    gps = State()
    confirm = State()


class SearchStation(StatesGroup):
    query = State()
