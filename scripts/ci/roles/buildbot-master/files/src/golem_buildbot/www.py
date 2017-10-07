from buildbot.plugins import util

from .settings import local_settings


www = dict(
    port=8010,
    plugins=dict(waterfall_view={}, console_view={}),
    auth=util.UserPasswordAuth({'maaktweluit@gmail.com': local_settings['worker_pass']}),
    authz=util.Authz(
        allowRules=[
            util.AnyControlEndpointMatcher(role="admins"),
        ],
        roleMatchers=[
            util.RolesFromEmails(admins=local_settings['admin_emails'])
        ]),
    change_hook_dialects={
        'github': {
            'strict': True,
            'secret': local_settings['github_webhook_secret'],
        },
    },
)
