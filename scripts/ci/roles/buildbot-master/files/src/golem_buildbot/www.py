from buildbot.plugins import util

from .settings import local_settings

# Testing auth for local instances
# _auth = util.UserPasswordAuth({'tst@mail.com': local_settings['worker_pass']})
# _authz = util.Authz(
#     allowRules=[
#         util.AnyControlEndpointMatcher(role="admins")
#     ],
#     roleMatchers=[
#         util.RolesFromEmails(admins=local_settings['admin_emails'])
#     ])


_auth = util.GitHubAuth(local_settings['github_client_id'],
                        local_settings['github_client_secret'],
                        apiVersion=4, getTeamsMembership=True)

_authz = util.Authz(
    allowRules=[
        util.AnyControlEndpointMatcher(role="golem")
    ],
    roleMatchers=[
        util.RolesFromGroups(groupPrefix='golemfactory/')
    ])


www = dict(
    port=8010,
    plugins=dict(waterfall_view={}, console_view={}),
    auth=_auth,
    authz=_authz,
    change_hook_dialects={
        'github': {
            'strict': True,
            'secret': local_settings['github_webhook_secret'],
        },
    },
)
