def get_skin_avatar_url(skin_id: str) -> str:
    skin_id = skin_id.replace('@', '%40')
    skin_id = skin_id.replace('#', '%23')
    return f'https://web.hycdn.cn/arknights/game/assets/char_skin/avatar/{skin_id}.png'


def get_skin_portrait_url(skin_id: str) -> str:
    skin_id = skin_id.replace('@', '%40')
    skin_id = skin_id.replace('#', '%23')
    return f'https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/{skin_id}.png'


def get_skill_icon_url(skill_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/char_skill/{skill_id}.png'


def get_tower_icon_url(tower_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/climb_tower/icon/{tower_id}.png'


def get_equip_icon_url(equip_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/uniequip/{equip_id}.png'


def get_equip_type_icon_url(equip_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/uniequip/type/icon/{equip_id}.png'


def get_equip_type_shining_url(color: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/uniequip/type/shining/{color}.png'


def get_skin_brand_logo_url(brand: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/brand/{brand}.png'


def get_zone_logo_url(zone_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/game_mode/campaign/zone_icon/{zone_id}.png'


def get_medal_url(medal_id: str) -> str:
    return f'https://web.hycdn.cn/arknights/game/assets/medal/{medal_id}.png'


def get_activity_logo_url(activity_id: str) -> str:
    return f'https://bbs.hycdn.cn/skland-fe-static/skland-rn/images/game-arknight/{activity_id}.png'


def get_rouge_banner_url(rouge_id: str) -> str:
    return f'https://bbs.hycdn.cn/skland-fe-static/skland-rn/images/game-arknight/{rouge_id}.png'
