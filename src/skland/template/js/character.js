const gamedataPath = '../../../resource/gamedata'

const changeGameDataSkinId = (skinId) => {
    skinId = skinId.replace(/@/g, '_')
    if (skinId.match(/_/g).length > 2) {
        skinId = skinId.replace(/#/g, '%23')
    } else {
        skinId = skinId.replace(/#/g, '_')
    }
    return skinId
}

const getSkinAvatarUrl = (skinId) => {
    skinId = skinId.replace(/@/g, '%40')
    skinId = skinId.replace(/#/g, '%23')
    return `https://web.hycdn.cn/arknights/game/assets/char_skin/avatar/${skinId}.png`
}

const getSkinPortraitUrl = (skinId) => {
    skinId = skinId.replace(/@/g, '%40')
    skinId = skinId.replace(/#/g, '%23')
    return `https://web.hycdn.cn/arknights/game/assets/char_skin/portrait/${skinId}.png`
}

const getSkillIconUrl = (skillId) => {
    return `https://web.hycdn.cn/arknights/game/assets/char_skill/${skillId}.png`
}

const getTowerIconUrl = (towerId) => {
    return `https://web.hycdn.cn/arknights/game/assets/climb_tower/icon/${towerId}.png`
}

const getEquipIconUrl = (equipId) => {
    return `https://web.hycdn.cn/arknights/game/assets/uniequip/${equipId}.png`
}

const getEquipTypeIconUrl = (equipId) => {
    return `https://web.hycdn.cn/arknights/game/assets/uniequip/type/icon/${equipId}.png`
}

const getEquipTypeShiningUrl = (color) => {
    return `https://web.hycdn.cn/arknights/game/assets/uniequip/type/shining/${color}.png`
}

const getSkinBrandLogoUrl = (brand) => {
    return `https://web.hycdn.cn/arknights/game/assets/brand/${brand}.png`
}

const getZoneLogoUrl = (zoneId) => {
    return `https://web.hycdn.cn/arknights/game/assets/game_mode/campaign/zone_icon/${zoneId}.png`
}

const getMedalUrl = (medalId) => {
    return `https://web.hycdn.cn/arknights/game/assets/medal/${medalId}.png`
}

const getActivityLogoUrl = (activityId) => {
    return `https://bbs.hycdn.cn/skland-fe-static/skland-rn/images/game-arknight/${activityId}.png`
}

const getRougeBannerUrl = (rougeId) => {
    return `https://bbs.hycdn.cn/skland-fe-static/skland-rn/images/game-arknight/${rougeId}.png`
}
