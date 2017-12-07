from buildbot.plugins import reporters, util

from .settings import local_settings


services = [
    reporters.GitHubStatusPush(
        builders=[
            'unittest-fast_control',
            'unittest_control',
            'buildpackage_control'],
        token=local_settings['github_api_token'],
        context=util.Interpolate('buildbot/%(prop:buildtype)s'),
        startDescription='Build started.',
        endDescription='Build done.')
]
