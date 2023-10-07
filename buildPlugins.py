import os
import sys
import json
import base64
import zipfile
import logging
import importlib

from amiyabot import PluginInstance
from amiyabot.util import temp_sys_path

sys.path += [os.path.dirname(os.path.abspath(__file__)) + '/../']
remote = 'plugins/official'


def build(dist, upload=False):
    if not os.path.exists(dist):
        os.makedirs(dist)

    profiles = []
    plugin_dir = []

    for root, dirs, files in os.walk(os.path.dirname(os.path.abspath(__file__)) + '/src'):
        is_plugin = False
        for exist in plugin_dir:
            if exist in root:
                is_plugin = True

        if is_plugin:
            continue

        for item in dirs:
            plugin: str = os.path.join(root, item)

            if not os.path.exists(f'{plugin}/__init__.py') or '__pycache__' in plugin:
                continue

            print(f'packaging... {plugin}')

            path_split = plugin.replace('\\', '/').split('/')
            parent_dir = os.path.abspath('/'.join(path_split[:-1]))

            with temp_sys_path(parent_dir):
                with temp_sys_path(plugin):
                    module = importlib.import_module(path_split[-1])
                    if not hasattr(module, 'bot'):
                        continue
                    instance: PluginInstance = getattr(module, 'bot')

            profile = {
                'name': instance.name,
                'version': instance.version,
                'plugin_id': instance.plugin_id,
                'plugin_type': instance.plugin_type,
                'description': instance.description,
                'document': instance.description,
                'logo': '',
            }

            doc = instance.document
            if doc and os.path.isfile(doc):
                with open(doc, mode='r', encoding='utf-8') as doc_file:
                    profile['document'] = doc_file.read()
            else:
                profile['document'] = doc

            if os.path.exists(os.path.join(plugin, 'logo.png')):
                with open(os.path.join(plugin, 'logo.png'), mode='rb') as logo:
                    profile['logo'] = 'data:image/png;base64,' + base64.b64encode(logo.read()).decode()

            profiles.append(profile)
            plugin_dir.append(plugin)

            package = f'{dist}/{instance.plugin_id}-{instance.version}.zip'

            with zipfile.ZipFile(package, 'w') as pack:
                for plugin_root, _, plugin_files in os.walk(plugin):
                    for index, filename in enumerate(plugin_files):
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

    cos = COSUploader(secret_id, secret_key, logger_level=logging.ERROR)

    cos.delete_folder(remote)
    for item in upload_progress(upload_list):
        cos.upload_file(*item)


def upload_progress(upload_list: list):
    count = len(upload_list)

    def print_bar(name: str = ''):
        p = int(curr / count * 100)
        block = int(p / 4)
        progress_line = '=' * block + ' ' * (25 - block)

        msg = f'uploading...{name}\nprogress: [{progress_line}] {curr}/{count} ({p}%)'

        print('\r', end='')
        print(msg, end='')

        sys.stdout.flush()

    curr = 0

    print_bar()
    for item in upload_list:
        yield item
        curr += 1
        print_bar(item[1])

    print()


if __name__ == '__main__':
    build('plugins')
