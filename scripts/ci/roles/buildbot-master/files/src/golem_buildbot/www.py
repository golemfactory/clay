# pylint: disable=import-error
from buildbot.www.hooks.github import GitHubEventHandler
from buildbot.plugins import util
# pylint: enable=import-error

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


class MyGitHubPrHandler(GitHubEventHandler):  # pylint: disable=R0903
    def handle_pull_request_review(self, payload, event):
        # Update event payload to match pull_request event, based on:
        # https://github.com/buildbot/buildbot/blob/master/master/buildbot/www/hooks/github.py # noqa pylint: disable=line-too-long
        payload['number'] = payload['pull_request']['number']
        payload['action'] = "synchronize"
        payload['pull_request']['commits'] = -1
        return self.handle_pull_request(payload, event)


www = dict(
    port=8010,
    plugins=dict(waterfall_view={}, console_view={}),
    auth=_auth,
    authz=_authz,
    change_hook_dialects={
        'github': {
            'strict': True,
            'secret': local_settings['github_webhook_secret'],
            'class': MyGitHubPrHandler,
        },
    },
)
