from buildbot.plugins import reporters, util

from .settings import local_settings


services = [
    reporters.GitHubStatusPush(
        token=local_settings['github_api_token'],
        context=util.Interpolate('buildbot/%(prop:buildername)s'),
        startDescription='Build started.',
        endDescription='Build done.')
]
