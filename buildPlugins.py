import os
import sys
import json
import zipfile
import importlib

from amiyabot import PluginInstance
from amiyabot.util import temp_sys_path

sys.path += [
    os.path.dirname(os.path.abspath(__file__)) + '/../'
]
remote = 'plugins/official'


def build(dist, upload=False):
    if not os.path.exists(dist):
        os.makedirs(dist)

    profiles = []
    for root, dirs, _ in os.walk(os.path.dirname(os.path.abspath(__file__)) + '/src'):
        for item in dirs:
            plugin = os.path.join(root, item)

            if not os.path.exists(f'{plugin}/__init__.py') or '__pycache__' in plugin:
                continue

            print(f'packaging... {plugin}')

            path_split = plugin.replace('\\', '/').split('/')
            parent_dir = os.path.abspath('/'.join(path_split[:-1]))

            with temp_sys_path(parent_dir):
                with temp_sys_path(plugin):
                    module = importlib.import_module(path_split[-1])
                    instance: PluginInstance = getattr(module, 'bot')

            profiles.append({
                'name': instance.name,
                'version': instance.version,
                'plugin_id': instance.plugin_id,
                'plugin_type': instance.plugin_type,
                'description': instance.description
            })

            package = f'{dist}/{instance.plugin_id}-{instance.version}.zip'

            with zipfile.ZipFile(package, 'w') as pack:
                for plugin_root, _, files in os.walk(plugin):
                    for index, filename in enumerate(files):
                        target = str(os.path.join(plugin_root, filename))
                        if '__pycache__' in target:
                            continue
                        pack.write(target, target.replace(plugin, '').strip('\\'))

            print(f'\t --> {package}')

    with open(f'{dist}/plugins.json', mode='w', encoding='utf-8') as file:
        file.write(json.dumps(profiles, ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': ')))

    if upload:
        upload_list = []
        for root, _, files in os.walk(dist):
            upload_list += [(os.path.join(root, file), f'{remote}/{file}') for file in files]

        upload_all_plugins(upload_list)


def upload_all_plugins(upload_list: list):
    from build.uploadFile import COSUploader

    secret_id = os.environ.get('SECRETID')
    secret_key = os.environ.get('SECRETKEY')

    cos = COSUploader(secret_id, secret_key)

    cos.delete_folder(remote)
    for item in upload_list:
        cos.upload_file(*item)


if __name__ == '__main__':
    build('plugins')
