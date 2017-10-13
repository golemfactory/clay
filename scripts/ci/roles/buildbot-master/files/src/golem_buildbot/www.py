from buildbot.plugins import util

from .settings import local_settings


www = dict(
    port=8010,
    plugins=dict(waterfall_view={}, console_view={}),
    auth=util.GitHubAuth(
        local_settings['github_client_id'],
        local_settings['github_client_secret'],
        apiVersion=4, getTeamsMembership=True),
    authz=util.Authz(
        allowRules=[
            util.AnyControlEndpointMatcher(role="golem"),
        ],
        roleMatchers=[
            util.RolesFromGroups(groupPrefix='golemfactory/')
        ]),
    change_hook_dialects={
        'github': {
            'strict': True,
            'secret': local_settings['github_webhook_secret'],
        },
    },
)
