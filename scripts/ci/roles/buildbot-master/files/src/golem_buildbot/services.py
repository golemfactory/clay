from buildbot.plugins import reporters, util

from .settings import local_settings


services = [
    reporters.GitHubStatusPush(
        builders=['fast_test', 'slow_test', 'buildpackage'],
        token=local_settings['github_api_token'],
        context=util.Interpolate('buildbot/%(prop:buildtype)s'),
        startDescription='Build started.',
        endDescription='Build done.')
]
