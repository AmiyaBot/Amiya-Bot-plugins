import re
import json

from core import log

from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource

from .core import register_blm_function

@register_blm_function
async def operator_info(operator_name:str) -> dict:
    """
    该函数可以用于获取干员的信息，包括其属性，技能等等，同时还能获取其对应的图片。

    :param operator_name: 干员的名称，例如“阿米娅”，必须为中文。
    :type operator_name: str

    :return: 一个字典，包含两个元素，“info”是包含干员数据的结构化字典。“image”是一个url，包含了一张排版好干员信息的图片，可供展示。
    :rtype: bool
    """

    operator_name = operator_name.strip()

    log.info(f"operator_info: {operator_name}")

    for name,opt in ArknightsGameData.operators.items():
        if name not in operator_name:
            continue

        detail_text = ""

        detail_text += "技力每秒恢复1点\n"

        stories = opt.stories()

        real_name = await ArknightsGameData.get_real_name(opt.origin_name)
        detail_text += f'干员代号:{opt.name} 干员真名:{real_name}\n'
        
        race_match = re.search(r'【种族】(.*?)\n', next(story["story_text"] for story in stories if story["story_title"] == "基础档案"))
        if race_match:
            race = race_match.group(1)
        else:
            race = "未知"
        detail_text = detail_text + f'职业:{opt.type} 种族:{race}\n'


        detail_text += next(story["story_text"]+"\n" for story in stories if story["story_title"] == "客观履历")

        opt_detail = opt.detail()[0]

        detail_text += f'最大生命:{opt_detail["maxHp"]} 攻击力:{opt_detail["atk"]} 防御力:{opt_detail["def"]} 法术抗性:{opt_detail["magicResistance"]}% 攻击间隔:{opt_detail["baseAttackTime"]}秒\n'

        detail_text +=f'干员特性:{opt_detail["operator_trait"]}\n'

        talents = opt.talents()

        talent_txt=""
        for i, talent in enumerate(talents, start=1):
            talent_name = talent["talents_name"]
            talent_desc = talent["talents_desc"]
            talent_txt += f"{i}天赋-{talent_name}:{talent_desc}"
            if i < len(talents):
                talent_txt += "。 "

        detail_text += f"{talent_txt}\n"

        skills, skills_id, skills_cost, skills_desc = opt.skills()

        for i in range(1, 4):
            matching_skill = next((skill for skill in skills if skill["skill_index"] == i), None)
            
            skill_txt = ""

            if matching_skill:
                skill_txt=f"{i}技能:"
                skill_txt = f"{matching_skill['skill_name']} "

                skill_desc = skills_desc[matching_skill['skill_no']]

                best_level = max([desc['skill_level'] for desc in skill_desc])
                best_desc = next((desc for desc in skill_desc if desc['skill_level'] == best_level), None)

                desc_text = re.sub(r'\[cl (.*?)@#.*? cle\]', lambda x: x.group(1), best_desc['description'])

                skill_txt+=f"初始技力:{best_desc['sp_init']} 技力消耗:{best_desc['sp_cost']} 持续时间:{best_desc['duration']} {desc_text}"
                
                skill_txt+="\n"
            
            detail_text += skill_txt

        detail_text += "\n"

        

        return {"info":detail_text,"image":"https://trpg.hsyhhssyy.net/deepcosplay-main-template/images/arknights/operator/"+opt.name+".png"}