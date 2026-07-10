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
    camera_ip = State()
    rtsp_url = State()
    qr = State()
    nfc = State()
    confirm = State()


class SearchStation(StatesGroup):
    query = State()
