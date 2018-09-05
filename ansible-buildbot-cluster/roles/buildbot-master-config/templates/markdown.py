# -*- python -*-
# ex: set filetype=python:

import os.path
from buildbot.plugins import *
import common

def enabled(step):
    if step.getProperty("npmConfigExists") == "True":
        return True
    else:
        return False

def generateDBTestStep(dbname, dbport):

    mysqlString = "mysql -u root -h 127.0.0.1 -P " + dbport

    return steps.ShellSequence(
        commands=[
            util.ShellArg(
                command='echo "select version()" | ' + mysqlString,
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='version'),
            util.ShellArg(
                command=util.Interpolate('echo "create database opencast%(prop:buildnumber)s;" | ' + mysqlString),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='createdb'),
            util.ShellArg(
                command=util.Interpolate(mysqlString + ' opencast%(prop:buildnumber)s < docs/scripts/ddl/mysql5.sql'),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='newdb'),
            util.ShellArg(
                command='bash docs/upgrade/.test.sh ' + dbport,
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile=dbname),
            util.ShellArg(
                command=util.Interpolate('echo "drop database opencast%(prop:buildnumber)s;" | ' + mysqlString),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='dropdb'),
        ],
        workdir="build/",
        name="Test database and migration scripts against " + dbname,
        haltOnFailure=False,
        flunkOnFailure=True)

def __getBasePipeline(): 

    enable = steps.SetPropertyFromCommand(
        command='[ -f docs/guides/package.json ] && echo True || echo False',
        property="npmConfigExists",
        name="Check mkdocs version support")

    check = steps.ShellSequence(
        commands=[
            util.ShellArg(
                command=['npm', 'install'],
                flunkOnFailure=True,
                haltOnFailure=True,
                logfile='npm_install'),
            util.ShellArg(
                command=['./node_modules/grunt/bin/grunt'],
                flunkOnFailure=True,
                haltOnFailure=True,
                logfile='grunt'),
        ],
        workdir="build/docs/guides",
        name="Check Markdown doc formatting",
        haltOnFailure=False,
        flunkOnFailure=True,
        doStepIf=enabled)

    build = steps.ShellSequence(
        commands=[
            util.ShellArg(
                command='cd admin && mkdocs build && cd ..',
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='admin'),
            util.ShellArg(
                command='cd developer && mkdocs build && cd ..',
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='developer'),
            util.ShellArg(
                command='cd user && mkdocs build && cd ..',
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='user'),
        ],
        workdir="build/docs/guides",
        name="Build Markdown docs",
        haltOnFailure=False,
        flunkOnFailure=True)


    f_build = util.BuildFactory()
    f_build.addStep(common.getClone())
    f_build.addStep(enable)
    f_build.addStep(check)
    f_build.addStep(build)
    f_build.addStep(generateDBTestStep("maria", "3307"))
    f_build.addStep(generateDBTestStep("mysql5.6", "3308"))
    f_build.addStep(generateDBTestStep("mysql5.7", "3309"))

    return f_build

def getPullRequestPipeline():

    f_build = __getBasePipeline()
    f_build.addStep(common.getClean())

    return f_build

def getBuildPipeline():

    masterPrep = steps.MasterShellCommand(
        command=["mkdir", "-p",
                util.Interpolate(os.path.normpath("{{ deployed_markdown }}")),
                util.Interpolate(os.path.normpath("{{ deployed_markdown_symlink_base }}")),
        ],
        name="Prep relevant directories on buildmaster")

    upload = steps.ShellSequence(
        commands=[
            util.ShellArg(
                command=util.Interpolate(
                    "scp -r admin/site {{ buildbot_scp_markdown }}/admin"),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='admin'),
            util.ShellArg(
                command=util.Interpolate(
                    "scp -r developer/site {{ buildbot_scp_markdown }}/developer"
                ),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='developer'),
            util.ShellArg(
                command=util.Interpolate(
                    "scp -r user/site {{ buildbot_scp_markdown }}/user"),
                flunkOnFailure=True,
                haltOnFailure=False,
                logfile='user'),
        ],
        workdir="build/docs/guides",
        name="Upload Markdown docs to buildmaster",
        haltOnFailure=True,
        flunkOnFailure=True,
        doStepIf=enabled)

    updateMarkdown = steps.MasterShellCommand(
        command=util.Interpolate(
            "rm -f {{ deployed_markdown_symlink }} && ln -s {{ deployed_markdown }} {{ deployed_markdown_symlink }}"
        ),
        name="Deploy Markdown")


    f_build = __getBasePipeline()
    f_build.addStep(masterPrep)
    f_build.addStep(common.getPermissionsFix())
    f_build.addStep(upload)
    f_build.addStep(updateMarkdown)
    f_build.addStep(common.getClean())

    return f_build
