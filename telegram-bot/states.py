from aiogram.fsm.state import State, StatesGroup


class AddStation(StatesGroup):
    code = State()
    name = State()
    region = State()
    address = State()
    vpn_ip = State()
    local_ip = State()
    rustdesk_id = State()
    gps = State()
    confirm = State()


class SearchStation(StatesGroup):
    query = State()
