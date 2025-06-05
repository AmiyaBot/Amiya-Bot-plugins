import json
import os
from typing import List
from PIL import Image
from io import BytesIO
import base64
import hashlib

from core.database.bot import Pool

from .logger import debug_log

pool_image = 'resource/plugins/gacha/pool'
custom_pool = 'resource/plugins/gacha/custom-pools'
custom_pool_image = 'resource/plugins/gacha/custom-pool-images'
custom_operator = 'resource/plugins/gacha/custom-pool-operators'


class CustomOperator:
    name = None
    rarity = None
    is_limit = None
    classes_code = None
    avatar = None
    portrait = None


def get_pool_name(pool: Pool):
    '''
    获取池子的用于显示给用户的名字
    '''
    return pool.pool_name


def get_pool_id(pool: Pool):
    '''
    获取池子的Id(用于存入UserGacha)
    '''
    if pool.is_official is None or pool.is_official:
        return pool.id
    else:
        return "Custom-" + pool.pool_uuid


def get_pool_selector(pool: Pool):
    '''
    获取用于聊天中选择池子的关键字
    对于官方池子，是池子的名字
    对于趣味池子，是"Custom-"+池子Guid (非官方池子的pool_name是Guid)
    '''
    if pool.is_official is None or pool.is_official:
        return pool.pool_name
    return "Custom-" + pool.pool_uuid


def get_pool_image(pool: Pool):
    '''
    获取卡池的题头图片
    '''
    pic = []
    pool_image_filename = pool.pool_name
    if pool.is_official == False:
        pool_image_filename = pool.pool_image
        debug_log(f"pool_image_filename: {pool_image_filename}")
        base_name_with_path, _ = os.path.splitext(pool_image_filename)
        base_name = os.path.basename(base_name_with_path)
        dir_name = os.path.dirname(pool_image_filename)
        for root, dirs, files in os.walk(dir_name):
            for file in files:
                if base_name in file:
                    pic.append(os.path.join(root, file))
    else:
        debug_log(f"pool_image_filename: {pool_image_filename}")
        for root, dirs, files in os.walk(pool_image):
            for file in files:
                if pool_image_filename in file:
                    pic.append(os.path.join(root, file))
    if pic:
        return pic[-1]
    else:
        return None


def copy_props(pool, data: dict):
    pool.pool_uuid = data.get("pool_uuid", None)
    pool.pool_name = data.get("pool_name", None)
    pool.pool_description = data.get("pool_description", None)
    pool.limit_pool = data.get("limit_pool", None)
    pool.is_classicOnly = data.get("is_classicOnly", None)
    pool.pickup_6 = data.get("pickup_6", None)
    pool.pickup_6_rate = data.get("pickup_6_rate", None)
    pool.pickup_s = data.get("pickup_s", None)
    pool.pickup_5 = data.get("pickup_5", None)
    pool.pickup_5_rate = data.get("pickup_5_rate", None)
    pool.pickup_s_5 = data.get("pickup_s_5", None)
    pool.pickup_4 = data.get("pickup_4", None)
    pool.pickup_4_rate = data.get("pickup_4_rate", None)
    pool.pickup_s_4 = data.get("pickup_s_4", None)
    pool.pickup_3 = data.get("pickup_3", None)
    pool.pickup_3_rate = data.get("pickup_3_rate", None)
    pool.pickup_s_3 = data.get("pickup_s_3", None)
    pool.pickup_2 = data.get("pickup_2", None)
    pool.pickup_2_rate = data.get("pickup_2_rate", None)
    pool.pickup_s_2 = data.get("pickup_s_2", None)
    pool.pickup_1 = data.get("pickup_1", None)
    pool.pickup_1_rate = data.get("pickup_1_rate", None)
    pool.pickup_s_1 = data.get("pickup_s_1", None)
    pool.version = data.get("version", None)


def get_official_pool(pool_id):
    return Pool.get_by_id(pool_id)


def save_image_from_base64(image_base64: str, output_file: str):
    try:
        # 首先移除output_file的扩展名，然后检测磁盘是否有任何图片文件与其匹配
        base_name_with_path, _ = os.path.splitext(output_file)  # 带路径的 base_name
        base_name = os.path.basename(base_name_with_path)
        dir_name = os.path.dirname(output_file)
        debug_log(f"base_name: {base_name}")
        for root, dirs, files in os.walk(dir_name):
            for file in files:
                if base_name in file:
                    debug_log(f"已存在图片文件 {file}，不再保存")
                    return os.path.join(root, file)

        image_data = base64.b64decode(image_base64)

        # 尝试打开图片数据
        image = Image.open(BytesIO(image_data))
        debug_log(f"图片格式为: {image.format}")

        # 确定图片的实际扩展名
        actual_extension = image.format.lower()

        # 替换 output_file 的扩展名为图片的实际格式
        output_file = os.path.join(dir_name, f"{base_name}.{actual_extension}")

        # 保存图片到指定路径
        image.save(output_file)
        debug_log(f"图片已保存为 {output_file}")
        return output_file
    except Exception as e:
        debug_log(f"无法识别图片格式: {e}")
        return None


def get_custom_pool(pool_selector):
    '''
    根据池子的Id(存在UserGacha里的内容)获取池子
    这里会自动判断是否是官方池子
    '''
    pool_id_str = str(pool_selector).lower()
    if pool_id_str.startswith("custom-"):
        # 初始化个性卡池
        # 切出uuid来
        pool_id_str = pool_id_str[7:]
        file_path = os.path.join(custom_pool, pool_id_str + '.json')
        if not os.path.exists(file_path):
            # 下载先不做
            debug_log("require download!" + file_path)
            return None
        else:
            debug_log("read from json!" + file_path)
            # 从json文件中读取
            pool = Pool()
            pool.is_official = False
            # 遍历每个attr, 看看json里有没有，有就读取到pool里
            with open(file_path, 'r') as f:
                data = json.load(f)
                copy_props(pool, data)

                if "pool_image_raw" in data:
                    # 将pool_image_raw的base64转成jpg落盘，注意原图可能为png或bmp
                    pool_image_filename = os.path.join(custom_pool_image, "Custom-" + pool.pool_uuid + "-PoolImage.png")
                    # 如果文件不存在，就保存
                    pool_image_filename = save_image_from_base64(data["pool_image_raw"], pool_image_filename)
                    pool.pool_image = pool_image_filename
                if "pool_image" in data:
                    pool.pool_image = data["pool_image"]
            # 额外处理custom_operators
            debug_log("pool name:" + pool.pool_name)
            pool.custom_operators = {}
            if "custom_operators" in data:
                # 遍历并落盘
                for operator_name in data["custom_operators"]:
                    operator_dict = data["custom_operators"][operator_name]

                    operator = CustomOperator()

                    operator.name = operator_name
                    operator.rarity = operator_dict['rarity']
                    operator.is_limit = operator_dict['is_limit']
                    operator.classes_code = operator_dict['classes_code']

                    operator_name_hash = hashlib.md5(operator_name.encode()).hexdigest()

                    operator_avatar_filename = os.path.join(
                        custom_operator, f"Custom{pool.pool_uuid}-Operator-{operator_name_hash}-Avatar.png"
                    )
                    operator_avatar_filename = save_image_from_base64(
                        operator_dict['avatar_raw'], operator_avatar_filename
                    )
                    operator.avatar = operator_avatar_filename

                    operator_portrait_filename = os.path.join(
                        custom_operator, f"Custom{pool.pool_uuid}-Operator-{operator_name_hash}-Portrait.png"
                    )
                    operator_portrait_filename = save_image_from_base64(
                        operator_dict['portrait_raw'], operator_portrait_filename
                    )
                    operator.portrait = operator_portrait_filename

                    pool.custom_operators[operator.name] = operator

                debug_log("custom_operators_count:" + str(len(pool.custom_operators)))
                debug_log("they are:")
                for name, operator in pool.custom_operators.items():
                    debug_log(
                        f"  - Name: {name}, Rarity: {operator.rarity}, Is Limit: {operator.is_limit}, Class: {operator.classes_code}, Avatar: {operator.avatar}, Portrait: {operator.portrait}"
                    )

            return pool
    return None
