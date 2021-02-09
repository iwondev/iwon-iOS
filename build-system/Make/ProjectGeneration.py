import json
import os
import shutil

from BuildEnvironment import is_apple_silicon, call_executable, BuildEnvironment


def remove_directory(path):
    if os.path.isdir(path):
        shutil.rmtree(path)


def generate(build_environment: BuildEnvironment, disable_extensions, disable_provisioning_profiles, configuration_path, bazel_app_arguments):
    project_path = os.path.join(build_environment.base_path, 'build-input/gen/project')
    app_target = 'Telegram'

    os.makedirs(project_path, exist_ok=True)
    remove_directory('{}/Tulsi.app'.format(project_path))
    remove_directory('{project}/{target}.tulsiproj'.format(project=project_path, target=app_target))

    tulsi_path = os.path.join(project_path, 'Tulsi.app/Contents/MacOS/Tulsi')

    if is_apple_silicon():
        tulsi_build_bazel_path = build_environment.bazel_x86_64_path
        if tulsi_build_bazel_path is None or not os.path.isfile(tulsi_build_bazel_path):
            print('Could not find a valid bazel x86_64 binary at {}'.format(tulsi_build_bazel_path))
            exit(1)
    else:
        tulsi_build_bazel_path = build_environment.bazel_path

    current_dir = os.getcwd()
    os.chdir(os.path.join(build_environment.base_path, 'build-system/tulsi'))
    call_executable([
        tulsi_build_bazel_path,
        'build', '//:tulsi',
        '--xcode_version={}'.format(build_environment.xcode_version),
        '--use_top_level_targets_for_symlinks',
        '--verbose_failures'
    ])
    os.chdir(current_dir)

    bazel_wrapper_path = os.path.abspath('build-input/gen/project/bazel')

    bazel_wrapper_arguments = []
    bazel_wrapper_arguments += ['--override_repository=build_configuration={}'.format(configuration_path)]

    with open(bazel_wrapper_path, 'wb') as bazel_wrapper:
        bazel_wrapper.write('''#!/bin/sh
{bazel} "$@" {arguments}
'''.format(
            bazel=build_environment.bazel_path,
            arguments=' '.join(bazel_wrapper_arguments)
        ).encode('utf-8'))

    call_executable(['chmod', '+x', bazel_wrapper_path])

    call_executable([
        'unzip', '-oq',
        'build-system/tulsi/bazel-bin/tulsi.zip',
        '-d', project_path
    ])

    user_defaults_path = os.path.expanduser('~/Library/Preferences/com.google.Tulsi.plist')
    if os.path.isfile(user_defaults_path):
        os.unlink(user_defaults_path)

    with open(user_defaults_path, 'wb') as user_defaults:
        user_defaults.write('''
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>defaultBazelURL</key>
        <string>{}</string>
</dict>
</plist>
'''.format(bazel_wrapper_path).encode('utf-8'))

    bazel_build_arguments = []
    bazel_build_arguments += ['--override_repository=build_configuration={}'.format(configuration_path)]
    if disable_extensions:
        bazel_build_arguments += ['--//Telegram:disableExtensions']
    if disable_provisioning_profiles:
        bazel_build_arguments += ['--//Telegram:disableProvisioningProfiles']

    call_executable([
        tulsi_path,
        '--',
        '--verbose',
        '--create-tulsiproj', app_target,
        '--workspaceroot', './',
        '--bazel', bazel_wrapper_path,
        '--outputfolder', project_path,
        '--target', '{target}:{target}'.format(target=app_target),
        '--build-options', ' '.join(bazel_build_arguments)
    ])

    additional_arguments = []
    additional_arguments += ['--override_repository=build_configuration={}'.format(configuration_path)]
    additional_arguments += bazel_app_arguments
    if disable_extensions:
        additional_arguments += ['--//Telegram:disableExtensions']

    additional_arguments_string = ' '.join(additional_arguments)

    tulsi_config_path = 'build-input/gen/project/{target}.tulsiproj/Configs/{target}.tulsigen'.format(target=app_target)
    with open(tulsi_config_path, 'rb') as tulsi_config:
        tulsi_config_json = json.load(tulsi_config)
    for category in ['BazelBuildOptionsDebug', 'BazelBuildOptionsRelease']:
        tulsi_config_json['optionSet'][category]['p'] += ' {}'.format(additional_arguments_string)
    tulsi_config_json['sourceFilters'] = [
        'Telegram/...',
        'submodules/...',
        'third-party/...'
    ]
    with open(tulsi_config_path, 'wb') as tulsi_config:
        tulsi_config.write(json.dumps(tulsi_config_json, indent=2).encode('utf-8'))

    call_executable([
        tulsi_path,
        '--',
        '--verbose',
        '--genconfig', '{project}/{target}.tulsiproj:{target}'.format(project=project_path, target=app_target),
        '--bazel', bazel_wrapper_path,
        '--outputfolder', project_path,
        '--no-open-xcode'
    ])

    xcodeproj_path = '{project}/{target}.xcodeproj'.format(project=project_path, target=app_target)

    bazel_build_settings_path = '{}/.tulsi/Scripts/bazel_build_settings.py'.format(xcodeproj_path)

    with open(bazel_build_settings_path, 'rb') as bazel_build_settings:
        bazel_build_settings_contents = bazel_build_settings.read().decode('utf-8')
    bazel_build_settings_contents = bazel_build_settings_contents.replace(
        'BUILD_SETTINGS = BazelBuildSettings(',
        'import os\nBUILD_SETTINGS = BazelBuildSettings('
    )
    bazel_build_settings_contents = bazel_build_settings_contents.replace(
        '\'--cpu=ios_arm64\'',
        '\'--cpu=ios_arm64\'.replace(\'ios_arm64\', \'ios_sim_arm64\' if os.environ.get(\'EFFECTIVE_PLATFORM_NAME\') '
        '== \'-iphonesimulator\' else \'ios_arm64\')'
    )
    with open(bazel_build_settings_path, 'wb') as bazel_build_settings:
        bazel_build_settings.write(bazel_build_settings_contents.encode('utf-8'))

    call_executable(['open', xcodeproj_path])
