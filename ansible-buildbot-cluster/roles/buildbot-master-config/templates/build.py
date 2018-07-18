# -*- python -*-
# ex: set filetype=python:

from buildbot.plugins import *
import os.path
import common


def __getBasePipeline():

    f_build = util.BuildFactory()
    f_build.addStep(common.getClone())
    f_build.addStep(common.getWorkerPrep())
    f_build.addStep(common.getBuild())

    return f_build

def getPullRequestPipeline():

    f_build = __getBasePipeline()
    f_build.addStep(common.getClean())

    return f_build

def getBuildPipeline():

    masterPrep = steps.MasterShellCommand(
        command=["mkdir", "-p",
                util.Interpolate(os.path.normpath("{{ deployed_builds }}")),
                util.Interpolate(os.path.normpath("{{ deployed_builds_symlink_base }}"))

        ],
        name="Prep relevant directories on buildmaster")

    #Note: We're using a string here because using the array disables shell globbing!
    uploadTarballs = steps.ShellCommand(
        command=util.Interpolate(
            "echo 'Opencast version %(prop:got_revision)s' | tee build/revision.txt && scp -r build/ {{ buildbot_scp_builds }}"),
        haltOnFailure=True,
        flunkOnFailure=True,
        name="Upload build to buildmaster")

    updateBuild = steps.MasterShellCommand(
        command=util.Interpolate(
            "rm -f {{ deployed_builds_symlink }} && ln -s {{ deployed_builds }} {{ deployed_builds_symlink }}"
        ),
        name="Deploy Build")

    updateCrowdin = steps.ShellCommand(
        command="if [ -f .upload-crowdin.sh] then CROWDIN_API_KEY=util.Secret('crowdin.key') bash .upload-crowdin.sh; fi",
        env={
            "CROWDIN_API_KEY": util.Secret("crowdin.key"),
            "TRAVIS_PULL_REQUEST": "false", #This is always false since the PR doesn't use this method
            "TRAVIS_BRANCH": util.Interpolate("%(prop:branch)s")
        },
	doStepIf={{ push_crowdin }},
	hideStepIf={{ not push_crowdin }},
        haltOnFailure=False,
        flunkOnFailure=True,
        name="Update Crowdin translation keys")

    f_build = __getBasePipeline()
    f_build.addStep(masterPrep)
    f_build.addStep(common.getPermissionsFix())
    f_build.addStep(uploadTarballs)
    f_build.addStep(updateBuild)
    f_build.addStep(updateCrowdin)
    f_build.addStep(common.getClean())

    return f_build
