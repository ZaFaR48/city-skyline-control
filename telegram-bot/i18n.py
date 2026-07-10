from __future__ import annotations


LANGUAGE_BY_BUTTON = {
    "🇹🇯 Тоҷикӣ": "tj",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
}

LANGUAGE_NAMES = {
    "tj": "Тоҷикӣ",
    "ru": "Русский",
    "en": "English",
}

MENU = {
    "tj": {
        "new_station": "📍 Стансияи нав",
        "search_station": "🔍 Ҷустуҷӯи стансия",
        "scan_qr": "📷 Скан кардани QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Камера",
        "network_status": "📊 Ҳолати шабака",
        "alerts": "🚨 Огоҳӣ",
        "reports": "📝 Ҳисобот",
        "settings": "⚙️ Танзимот",
    },
    "ru": {
        "new_station": "📍 Новая станция",
        "search_station": "🔍 Поиск станции",
        "scan_qr": "📷 Сканировать QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Камера",
        "network_status": "📊 Состояние сети",
        "alerts": "🚨 Оповещения",
        "reports": "📝 Отчеты",
        "settings": "⚙️ Настройки",
    },
    "en": {
        "new_station": "📍 New station",
        "search_station": "🔍 Search station",
        "scan_qr": "📷 Scan QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Camera",
        "network_status": "📊 Network status",
        "alerts": "🚨 Alerts",
        "reports": "📝 Reports",
        "settings": "⚙️ Settings",
    },
}

TEXT = {
    "tj": {
        "welcome": "👋 Хуш омадед!\n\nCity Skyline Control Center\n\nЛутфан забони худро интихоб кунед.",
        "language_selected": "✅ Забони тоҷикӣ интихоб шуд.",
        "main_menu": "Менюи асосӣ:",
        "cancel": "❌ Бекор кардан",
        "save": "✅ Сабт кардан",
        "skip": "⏭ Skip",
        "send_location": "📍 Ирсоли ҷойгиршавӣ",
        "generate_qr": "📷 Generate QR",
        "assign_nfc": "🏷 Assign NFC",
        "cancelled": "Амалиёт бекор шуд.",
        "enter_code": "Рақами расмии стансияро ворид кунед.\n\nМисол: 10042",
        "enter_name": "Номи стансияро ворид кунед.",
        "enter_region": "Минтақаро ворид кунед.",
        "enter_address": "Адресро ворид кунед.",
        "enter_vpn": "VPN IP ворид кунед ё Skip.",
        "enter_local": "Local IP ворид кунед ё Skip.",
        "enter_rustdesk": "RustDesk ID ворид кунед ё Skip.",
        "enter_location": "GPS ҷойгиршавиро фиристед ё Skip.",
        "enter_camera_ip": "Camera IP ворид кунед ё Skip.",
        "enter_rtsp": "RTSP URL ворид кунед ё Skip.",
        "enter_qr": "QR Generate ё Skip.",
        "enter_nfc": "NFC Assign ё Skip.",
        "invalid_required": "Ин майдон ҳатмист. Лутфан арзиш ворид кунед.",
        "invalid_ip": "IP нодуруст аст. Лутфан IP дуруст ворид кунед ё Skip.",
        "invalid_location": "Лутфан ҷойгиршавиро бо тугма фиристед ё Skip.",
        "summary_title": "Лутфан маълумотро тасдиқ кунед:",
        "missing_backend": "Backend currently requires VPN IP, Local IP and GPS before saving. Please fill them or ask admin to enable draft stations.",
        "missing_fields": "Майдонҳои намерасида:",
        "saved": "✅ Стансия сабт шуд.",
        "station_created_camera": "Камера низ сабт шуд.",
        "station_created_no_camera": "Камера сабт нашуд, чун Camera IP ё RTSP URL ворид нашуд.",
        "api_error": "❌ Хатои backend:",
        "search_prompt": "Матни ҷустуҷӯро ворид кунед: код, ном, IP ё адрес.",
        "search_empty": "Матни ҷустуҷӯ холӣ аст.",
        "search_no_results": "Стансия ёфт нашуд.",
        "search_results": "Натиҷаҳои ҷустуҷӯ:",
        "not_implemented": "Ин қисм ҳоло танҳо дар меню фаъол аст.",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать!\n\nCity Skyline Control Center\n\nПожалуйста, выберите язык.",
        "language_selected": "✅ Русский язык выбран.",
        "main_menu": "Главное меню:",
        "cancel": "❌ Отмена",
        "save": "✅ Сохранить",
        "skip": "⏭ Skip",
        "send_location": "📍 Отправить геолокацию",
        "generate_qr": "📷 Generate QR",
        "assign_nfc": "🏷 Assign NFC",
        "cancelled": "Операция отменена.",
        "enter_code": "Введите официальный код станции.\n\nПример: 10042",
        "enter_name": "Введите название станции.",
        "enter_region": "Введите регион.",
        "enter_address": "Введите адрес.",
        "enter_vpn": "Введите VPN IP или Skip.",
        "enter_local": "Введите Local IP или Skip.",
        "enter_rustdesk": "Введите RustDesk ID или Skip.",
        "enter_location": "Отправьте GPS-локацию или Skip.",
        "enter_camera_ip": "Введите Camera IP или Skip.",
        "enter_rtsp": "Введите RTSP URL или Skip.",
        "enter_qr": "QR Generate или Skip.",
        "enter_nfc": "NFC Assign или Skip.",
        "invalid_required": "Это обязательное поле. Введите значение.",
        "invalid_ip": "Некорректный IP. Введите правильный IP или Skip.",
        "invalid_location": "Отправьте геолокацию кнопкой или нажмите Skip.",
        "summary_title": "Проверьте данные перед сохранением:",
        "missing_backend": "Backend currently requires VPN IP, Local IP and GPS before saving. Please fill them or ask admin to enable draft stations.",
        "missing_fields": "Не хватает полей:",
        "saved": "✅ Станция сохранена.",
        "station_created_camera": "Камера тоже сохранена.",
        "station_created_no_camera": "Камера не сохранена: не указан Camera IP или RTSP URL.",
        "api_error": "❌ Ошибка backend:",
        "search_prompt": "Введите запрос: код, название, IP или адрес.",
        "search_empty": "Пустой поисковый запрос.",
        "search_no_results": "Станции не найдены.",
        "search_results": "Результаты поиска:",
        "not_implemented": "Этот раздел пока доступен только в меню.",
    },
    "en": {
        "welcome": "👋 Welcome!\n\nCity Skyline Control Center\n\nPlease choose your language.",
        "language_selected": "✅ English selected.",
        "main_menu": "Main menu:",
        "cancel": "❌ Cancel",
        "save": "✅ Save",
        "skip": "⏭ Skip",
        "send_location": "📍 Send location",
        "generate_qr": "📷 Generate QR",
        "assign_nfc": "🏷 Assign NFC",
        "cancelled": "Operation cancelled.",
        "enter_code": "Enter the official station code.\n\nExample: 10042",
        "enter_name": "Enter the station name.",
        "enter_region": "Enter the region.",
        "enter_address": "Enter the address.",
        "enter_vpn": "Enter VPN IP or Skip.",
        "enter_local": "Enter Local IP or Skip.",
        "enter_rustdesk": "Enter RustDesk ID or Skip.",
        "enter_location": "Send GPS location or Skip.",
        "enter_camera_ip": "Enter Camera IP or Skip.",
        "enter_rtsp": "Enter RTSP URL or Skip.",
        "enter_qr": "QR Generate or Skip.",
        "enter_nfc": "NFC Assign or Skip.",
        "invalid_required": "This field is required. Please enter a value.",
        "invalid_ip": "Invalid IP. Enter a valid IP or Skip.",
        "invalid_location": "Please send location with the button or choose Skip.",
        "summary_title": "Please confirm the station details:",
        "missing_backend": "Backend currently requires VPN IP, Local IP and GPS before saving. Please fill them or ask admin to enable draft stations.",
        "missing_fields": "Missing fields:",
        "saved": "✅ Station saved.",
        "station_created_camera": "Camera was saved too.",
        "station_created_no_camera": "Camera was not saved because Camera IP or RTSP URL was not provided.",
        "api_error": "❌ Backend error:",
        "search_prompt": "Enter search text: code, name, IP or address.",
        "search_empty": "Search text is empty.",
        "search_no_results": "No stations found.",
        "search_results": "Search results:",
        "not_implemented": "This section is currently menu-only.",
    },
}


def lang_or_default(lang: str | None) -> str:
    return lang if lang in TEXT else "tj"


def t(lang: str | None, key: str) -> str:
    selected = lang_or_default(lang)
    return TEXT[selected].get(key, TEXT["tj"][key])


def menu_label(lang: str | None, key: str) -> str:
    selected = lang_or_default(lang)
    return MENU[selected][key]


def all_menu_labels(key: str) -> set[str]:
    return {labels[key] for labels in MENU.values()}


def all_texts(key: str) -> set[str]:
    return {labels[key] for labels in TEXT.values()}
