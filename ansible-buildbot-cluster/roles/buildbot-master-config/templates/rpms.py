# -*- python -*-
# ex: set filetype=python:

import os.path
from buildbot.plugins import *
import common

profiles = ["admin", "adminpresentation", "adminworker", "allinone", "ingest", "migration", "presentation", "worker"]

def wasCloned(step):
    if step.getProperty("alreadyCloned") == "True":
        return True
    else:
        return False


def wasNotCloned(step):
    return not wasCloned(step)


def hideIfAlreadyCloned(results, step):
    return wasCloned(step)


def hideIfNotAlreadyCloned(results, step):
    return wasNotCloned(step)

def getRPMBuilds():
    builds = []
    for profile in profiles:
        builds.append(util.ShellArg(
                command=[
                    'rpmbuild',
                    '--define', 'ocdist ' + profile,
                    '--define', util.Interpolate('tarversion %(prop:major_version)s-SNAPSHOT'),
                    '-bb', '--noclean',
                    util.Interpolate("SPECS/opencast%(prop:major_version)s.spec")
                ],
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="" + profile))
    return builds


def getBuildPipeline():

    rpmChecker = steps.SetPropertyFromCommand(
        command="[ -d .git ] && echo True || echo False",
        property="alreadyCloned",
        name="Checking if this is a fresh clone")

    rpmsClone = steps.ShellCommand(
        command=[
            'git', 'clone', "{{ source_rpm_repo_url }}", './'
        ],
        flunkOnFailure=True,
        haltOnFailure=True,
        doStepIf=wasNotCloned,
        hideStepIf=hideIfAlreadyCloned,
        name="Cloning rpm packaging configs")

    rpmsUpdate = steps.ShellSequence(
        commands=[
            util.ShellArg(
                command=['git', 'fetch'],
                flunkOnFailure=True,
                haltOnFailure=True,
                logfile='fetch'),
            util.ShellArg(
                command=[
                    'git', 'reset', '--hard',
                    util.Interpolate('origin/master')
                ],
                flunkOnFailure=True,
                haltOnFailure=True,
                logfile='checkout')
        ],
        workdir="build",
        flunkOnFailure=True,
        haltOnFailure=True,
        doStepIf=wasCloned,
        hideStepIf=hideIfNotAlreadyCloned,
        name="Resetting rpm packaging configs")

    rpmsVersion = steps.SetPropertyFromCommand(
        command="git rev-parse HEAD",
        property="rpm_script_rev",
        flunkOnFailure=True,
        warnOnFailure=True,
        haltOnFailure=True,
        workdir="build",
        name="Get rpm script revision")

    rpmsPrep = steps.ShellSequence(
        commands=[
            util.ShellArg(
                command=[
                    'rpmdev-bumpspec', '-s',
                    util.Interpolate(
                        '%(prop:got_revision)s'),
                    '-u', '"Buildbot <buildbot@opencast.org>"',
                    '-c',
                    util.Interpolate(
                        'Build revision %(prop:got_revision)s, built with %(prop:rpm_script_rev)s scripts'
                    ),
                    util.Interpolate('opencast%(prop:major_version)s.spec')
                ],
                flunkOnFailure=True,
                warnOnFailure=True,
                logfile='rpmdev-bumpspec'),
        ],
        workdir="build/specs",
        name="Prepping rpms",
        haltOnFailure=True,
        flunkOnFailure=True)

    rpmsFetch = steps.ShellSequence(
        commands=[
            util.ShellArg(
			    #We're using a string here rather than an arg array since we need the shell functions
                command='echo -e "%_topdir `pwd`" > ~/.rpmmacros',
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="rpmdev-setup"),
            util.ShellArg(
                command=[
                    'rpmdev-setuptree'
                ],
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="rpmdev"),
            util.ShellArg(
                command=[
                    'mkdir', '-p',
                    'BUILD/opencast/build',
                ],
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="prep"),
            util.ShellArg(
                command=[
                    "scp",
                    util.Interpolate("{{ buildbot_scp_builds }}/*.tar.gz"),
                    "BUILD/opencast/build"
                ],
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="download"),
            util.ShellArg(
                command=[
                    "ln", "-sr",
                    util.Interpolate("opencast%(prop:major_version)s.spec"),
                    "SPECS"
                ],
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="specs"),
            util.ShellArg(
                #Same here
                command=util.Interpolate("ln -sr opencast%(prop:major_version)s/* SOURCES"),
                haltOnFailure=True,
                flunkOnFailure=True,
                logfile="sources")
        ],
        workdir="build/specs",
        name="Fetch built artifacts and build prep",
        haltOnFailure=True,
        flunkOnFailure=True)

    rpmsBuild = steps.ShellSequence(
        commands=getRPMBuilds(),
        workdir="build/specs",
        name="Build rpms",
        haltOnFailure=True,
        flunkOnFailure=True)

    masterPrep = steps.MasterShellCommand(
        command=["mkdir", "-p",
                util.Interpolate(os.path.normpath("{{ deployed_rpms }}")),
                util.Interpolate(os.path.normpath("{{ deployed_rpms_symlink_base }}"))
        ],
        name="Prep relevant directories on buildmaster")

    #Note: We're using a string here because using the array disables shell globbing!
    rpmsUpload = steps.ShellCommand(
        command=util.Interpolate(
            "scp -r RPMS/noarch/ {{ buildbot_scp_rpms }}"
        ),
        workdir="build/specs",
        haltOnFailure=True,
        flunkOnFailure=True,
        name="Upload rpms to buildmaster")

    rpmsDeploy = steps.MasterShellCommand(
        command=util.Interpolate(
            "rm -f {{ deployed_rpms_symlink }} && ln -s {{ deployed_rpms }} {{ deployed_rpms_symlink }}"
        ),
        name="Deploy rpms")

    f_package_rpms = util.BuildFactory()
    f_package_rpms.addStep(rpmChecker)
    f_package_rpms.addStep(rpmsClone)
    f_package_rpms.addStep(rpmsUpdate)
    f_package_rpms.addStep(rpmsVersion)
    f_package_rpms.addStep(rpmsPrep)
    f_package_rpms.addStep(rpmsFetch)
    f_package_rpms.addStep(rpmsBuild)
    #f_package_rpms.addStep(masterPrep)
    f_package_rpms.addStep(rpmsUpload)
    f_package_rpms.addStep(rpmsDeploy)
    f_package_rpms.addStep(common.getClean())

    return f_package_rpms
