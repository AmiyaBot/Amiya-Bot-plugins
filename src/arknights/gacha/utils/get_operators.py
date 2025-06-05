from core.resource.arknightsGameData import ArknightsGameData
from .logger import debug_log


def get_operators(classic_only: bool = False):
    opts = []
    for name, item in ArknightsGameData.operators.items():
        if classic_only:
            if item.is_classic:
                # 其实应该是 not item.limit and not item.unavailable and item.is_classic
                # 但是目前 is_classic 为 True 的必是卡池干员，所以暂时不需要这么长的判断
                opts.append(item)
        else:
            classic_opt = item.is_classic and item.rarity >= 5
            if not item.limit and not item.unavailable and not classic_opt:
                if "预备干员" in item.name:
                    debug_log(f"预备干员: {item}")
                opts.append(item)

    return opts


def get_operator_by_names(names: list):
    opts = []
    for item in ArknightsGameData.operators.values():
        for name in names:
            # 判断方式operator["name"] = name
            if item["name"] == name:
                opts.append(item)
                break

    return opts
