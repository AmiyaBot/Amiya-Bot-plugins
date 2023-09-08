const gamedataPath = '../../../'

const classesIcons = {
    '术师': 'caster.png',
    '医疗': 'medic.png',
    '先锋': 'pioneer.png',
    '狙击': 'sniper.png',
    '特种': 'special.png',
    '辅助': 'support.png',
    '重装': 'tank.png',
    '近卫': 'warrior.png'
}

const spType = {
    'INCREASE_WITH_TIME': '自动回复',
    'INCREASE_WHEN_ATTACK': '攻击回复',
    'INCREASE_WHEN_TAKEN_DAMAGE': '受击回复',
    8: '被动'
}

const skillType = {
    'PASSIVE': '被动',
    'MANUAL': '手动触发',
    'AUTO': '自动触发'
}

const skillLevel = {
    8: '专精一',
    9: '专精二',
    10: '专精三'
}

function colorSpan(text, tag = true) {
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace(/\n/g, '<br/>')
    text = text.replace(/\s/g, '')
    text = text.replace(/\[cl/g, tag ? '<span class="mark">' : '')
    text = text.replace(/@#174CC6cle]/g, tag ? '</span>' : '')

    return text
}

function range(text) {
    let lines = []
    for (let line of text.split('\n')) {
        let items = []
        for (let char of line) {
            switch (char) {
                case '　':
                    items.push('<div class="block"></div>')
                    break
                case '□':
                    items.push('<div class="block r"></div>')
                    break
                case '■':
                    items.push('<div class="block s"></div>')
                    break
            }
        }
        lines.push(`<div class="block-group">${items.join('')}</div>`)
    }
    return lines.join('')
}

function itemIconPath(itemIcon) {
    return gamedataPath + 'resource/gamedata/item/' + itemIcon + '.png'
}

function avatarIconPath(avatarIcon) {
    return gamedataPath + 'resource/gamedata/avatar/' + avatarIcon + '.png'
}

function skillIconPath(skillIcon) {
    return gamedataPath + 'resource/gamedata/skill/' + skillIcon + '.png'
}

function buildingSkillIconPath(bsIcon) {
    return gamedataPath + 'resource/gamedata/building_skill/' + bsIcon + '.png'
}
