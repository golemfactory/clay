import requests
from twisted.internet import defer

# pylint: disable=E0401
from buildbot.plugins import steps, util
from buildbot.process import results
from buildbot.reporters import utils as reporters_utils
# pylint: enable=E0401


from .builders_util import extract_rev


class ControlStepFactory():
    @staticmethod
    def hook_pr():

        @util.renderer
        def extract_pr_data(props):
            pr_number = props.getProperty('branch').split('/')[2]
            run_slow = True

            # config vars
            required_approvals = 1

            class ApprovalError(Exception):
                pass

            base_url = "https://api.github.com/" \
                "repos/maaktweluit/golem/pulls/{}/reviews"
            url = base_url.format(pr_number)

            try:
                # Github API requires user agent.
                req = requests.get(url, headers={'User-Agent': 'build-bot'})

                json_data = req.json()

                if "message" in json_data \
                        and json_data["message"].startswith("API rate"):

                    print("Raw reply:{}".format(json_data))
                    raise ApprovalError

                check_states = ["APPROVED", "CHANGES_REQUESTED"]
                review_states = [
                    a for a in json_data if a["state"] in check_states]
                unique_reviews = {
                    x['user']['login']: x for x in review_states}.values()

                result = [a for a in unique_reviews if a["state"] == "APPROVED"]
                approvals = len(result)
                run_slow = approvals >= required_approvals
            except(requests.HTTPError, requests.Timeout, ApprovalError) as e:
                print("Error calling github, run all tests. {}".format(url))

            return {'runslow': '--runslow' if run_slow else ''}

        def is_slow(step):
            return step.getProperty('runslow') != ''

        factory = util.BuildFactory()
        # Check approvals
        factory.addStep(steps.SetProperties(properties=extract_pr_data))
        # Trigger test
        factory.addStep(
            steps.Trigger(schedulerNames=['control_test'],
                          waitForFinish=True,
                          # hideStepIf=is_fast,
                          haltOnFailure=True,
                          set_properties={
                              'runslow': util.Interpolate('%(prop:runslow)s')
                          }))
        # Trigger buildpackage if >= 1
        factory.addStep(
            steps.Trigger(schedulerNames=['control_build'],
                          waitForFinish=False,
                          doStepIf=is_slow,
                          # hideStepIf=is_fast,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def hook_push():
        factory = util.BuildFactory()
        # Ensure slow tests are triggered
        factory.addStep(steps.SetProperty(property='runslow',
                                          value='--runslow'))
        # Trigger test
        factory.addStep(
            steps.Trigger(schedulerNames=['control_test'],
                          waitForFinish=True,
                          haltOnFailure=True,
                          set_properties={
                              'runslow': util.Interpolate('%(prop:runslow)s')
                          }))
        # Trigger buildpackage
        factory.addStep(
            steps.Trigger(schedulerNames=['control_build'],
                          waitForFinish=False,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def control_test():
        factory = util.BuildFactory()
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'linttest',
                    'unittest_macOS',
                    'unittest_linux',
                    'unittest_windows'],
                waitForFinish=True,
                haltOnFailure=True,
                set_properties={
                    'runslow': util.Interpolate('%(prop:runslow)s')
                }))
        return factory

    @staticmethod
    def control_build():
        def set_version_property(result, step):
            print("step: {}".format(step))
            print("build: {}".format(step.build))
            return False

        factory = util.BuildFactory()
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'buildpackage_macOS',
                    'buildpackage_linux',
                    'buildpackage_windows'],
                waitForFinish=True,
                haltOnFailure=True,
                hideStepIf=set_version_property))
        return factory

    @staticmethod
    def hook_nightly():

        @util.renderer
        @defer.inlineCallbacks
        def get_last_nightly(step):

            @defer.inlineCallbacks
            def get_last_buildpackage_success(cur_build):

                # Get builderId and buildNumber to scan succesfull builds
                builder_id = yield cur_build.master.db.builders.findBuilderId(
                    'control_build', autoCreate=False)
                builds = yield cur_build.master.db.builds.getBuilds(
                    builderid=builder_id, complete=True)
                # this is the first build
                i = len(builds)
                if builds is None or i == 0:
                    print("No previous build to check success")
                    defer.returnValue(True)
                    return True

                last_i = len(builds)

                while last_i != 0:
                    last_i -= 1
                    build = builds[last_i]
                    if build['results'] == results.SUCCESS:
                        print("Successful build {}".format(build))
                        build = yield cur_build.master.data.get(
                            ("builders", build['builderid'],
                             "builds", build['number']))
                        print("Successful build {}".format(build))
                        yield reporters_utils.getDetailsForBuild(
                            cur_build.master,
                            build,
                            wantProperties=True)
                        print("Found previous succes, skipping build")
                        print("Successful build {}".format(build))
                        rev = extract_rev(build['properties'])
                        print("rev found: {}".format(rev))

                        defer.returnValue(rev[:8])
                        return False

                print("No previous success, run build")
                defer.returnValue(True)
                return True

            def is_uploaded_to_github(sha):

                base_url = "https://api.github.com/" \
                           "repos/maaktweluit/golem/releases"

                try:
                    # Github API requires user agent.
                    req = requests.get(
                        base_url, headers={'User-Agent': 'build-bot'})

                    if "API rate" in req.text:
                        print("Raw reply:{}".format(req.text))
                        raise Exception("Cant get latest release from github")

                    # Check if SHA to upload is on the return data
                    return sha in req.text
                except(requests.HTTPError, requests.Timeout) as e:
                    print("Error calling github, run all tests."
                          " {} - {}".format(base_url, e))

                return False

            print("Nightly hook")
            master_result = yield get_last_buildpackage_success(step.build)
            print("Master result: {}".format(master_result))
            github_result = is_uploaded_to_github(master_result)
            print("Githuib result: {}".format(github_result))
            defer.returnValue({
                'same_as_github': github_result,
                'last_nightly_build': master_result
            })

        def is_not_same(step):
            return not step.getProperty('same_as_github')

        def store_master_result(result, step):
            print("result: {}".format(result))
            print("step: {}".format(step))
            return False

        nightly_branch = 'refs/pull/4/merge'

        factory = util.BuildFactory()

        # Get last nights SHA from github releases
        # Get last successfull develop package from artefact dir
        # Exit success when SHA's are the same
        factory.addStep(steps.SetProperties(properties=get_last_nightly))
        factory.addStep(steps.MasterShellCommand(
            command="ls | grep %(prop:last_nightly_build)s",
            workdir="/var/build-artifacts/{}".format(nightly_branch),
            hideStepIf=store_master_result,
            doStepIf=is_not_same))

        # Get all packages from last successfull develop build
        # factory.addStep(download all 3 packages, doStepIf=is_not_same)
        # Upload to github nightly repository as release
        # factory.addStep(upload all 3 packages, doStepIf=is_not_same)

        return factory
