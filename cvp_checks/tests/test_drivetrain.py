import jenkins
from xml.dom import minidom
from cvp_checks import utils
import json
import pytest
import time
import os
from pygerrit2 import GerritRestAPI, HTTPBasicAuth
from requests import HTTPError
import git

def join_to_gerrit(local_salt_client, gerrit_user, gerrit_password):
    gerrit_port = local_salt_client.cmd(
        'I@gerrit:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_gerrit_bind_port'],
        expr_form='compound').values()[0]
    gerrit_address = local_salt_client.cmd(
        'I@gerrit:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_gerrit_bind_host'],
        expr_form='compound').values()[0]
    url = 'http://{0}:{1}'.format(gerrit_address,gerrit_port)
    auth = HTTPBasicAuth(gerrit_user, gerrit_password)
    rest = GerritRestAPI(url=url, auth=auth)
    return rest

def join_to_jenkins(local_salt_client, jenkins_user, jenkins_password):
    jenkins_port = local_salt_client.cmd(
        'I@jenkins:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_jenkins_bind_port'],
        expr_form='compound').values()[0]
    jenkins_address = local_salt_client.cmd(
        'I@jenkins:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_jenkins_bind_host'],
        expr_form='compound').values()[0]
    jenkins_url = 'http://{0}:{1}'.format(jenkins_address,jenkins_port)
    server = jenkins.Jenkins(jenkins_url, username=jenkins_user, password=jenkins_password)
    return server

def get_password(local_salt_client,service):
    password = local_salt_client.cmd(
        service,
        'pillar.get',
        ['_param:openldap_admin_password'],
        expr_form='pillar').values()[0]
    return password

def test_drivetrain_gerrit(local_salt_client):
    gerrit_password = get_password(local_salt_client,'gerrit:client')
    gerrit_error = ''
    current_date = time.strftime("%Y%m%d-%H.%M.%S", time.localtime())
    test_proj_name = "test-dt-{0}".format(current_date)
    gerrit_port = local_salt_client.cmd(
        'I@gerrit:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_gerrit_bind_port'],
        expr_form='compound').values()[0]
    gerrit_address = local_salt_client.cmd(
        'I@gerrit:client and not I@salt:master',
        'pillar.get',
        ['_param:haproxy_gerrit_bind_host'],
        expr_form='compound').values()[0]
    try:
        #Connecting to gerrit and check connection
        server = join_to_gerrit(local_salt_client,'admin',gerrit_password)
        gerrit_check = server.get("/changes/?q=owner:self%20status:open")
        #Check deleteproject plugin and skip test if the plugin is not installed
        gerrit_plugins = server.get("/plugins/?all")
        if 'deleteproject' not in gerrit_plugins:
            pytest.skip("Delete-project plugin is not installed")
        #Create test project and add description
        server.put("/projects/"+test_proj_name)
        server.put("/projects/"+test_proj_name+"/description",json={"description":"Test DriveTrain project","commit_message": "Update the project description"})
    except HTTPError, e:
        gerrit_error = e
    try:
        #Create test folder and init git
        repo_dir = os.path.join(os.getcwd(),test_proj_name)
        file_name = os.path.join(repo_dir, current_date)
        repo = git.Repo.init(repo_dir)
        #Add remote url for this git repo
        origin = repo.create_remote('origin', 'http://admin:{1}@{2}:{3}/{0}.git'.format(test_proj_name,gerrit_password,gerrit_address,gerrit_port))
        #Add commit-msg hook to automatically add Change-Id to our commit
        os.system("curl -Lo {0}/.git/hooks/commit-msg 'http://admin:{1}@{2}:{3}/tools/hooks/commit-msg' > /dev/null 2>&1".format(repo_dir,gerrit_password,gerrit_address,gerrit_port))
        os.system("chmod u+x {0}/.git/hooks/commit-msg".format(repo_dir))
        #Create a test file
        f = open(file_name, 'w+')
        f.write("This is a test file for DriveTrain test")
        f.close()
        #Add file to git and commit it to Gerrit for review
        repo.index.add([file_name])
        repo.index.commit("This is a test commit for DriveTrain test")
        repo.git.push("origin", "HEAD:refs/for/master")
        #Get change id from Gerrit. Set Code-Review +2 and submit this change
        changes = server.get("/changes/?q=project:{0}".format(test_proj_name))
        last_change = changes[0].get('change_id')
        server.post("/changes/{0}/revisions/1/review".format(last_change),json={"message":"All is good","labels":{"Code-Review":"+2"}})
        server.post("/changes/{0}/submit".format(last_change))
    except HTTPError, e:
        gerrit_error = e
    finally:
        #Delete test project
        server.post("/projects/"+test_proj_name+"/deleteproject~delete")
    assert gerrit_error == '',\
        'Something is wrong with Gerrit'.format(gerrit_error)


def test_drivetrain_jenkins_job(local_salt_client):
    jenkins_password = get_password(local_salt_client,'jenkins:client')
    server = join_to_jenkins(local_salt_client,'admin',jenkins_password)
    #Getting Jenkins test job name from configuration
    config = utils.get_configuration()
    jenkins_test_job = config['jenkins_test_job']
    if not jenkins_test_job or jenkins_test_job == '':
        jenkins_test_job = 'git-mirror-downstream-mk-pipelines'
    if server.get_job_name(jenkins_test_job):
        next_build_num = server.get_job_info(jenkins_test_job)['nextBuildNumber']
        #If this is first build number skip building check
        if next_build_num != 1:
            #Check that test job is not running at this moment,
            #Otherwise skip the test
            last_build_num = server.get_job_info(jenkins_test_job)['lastBuild'].get('number')
            last_build_status = server.get_build_info(jenkins_test_job,last_build_num)['building']
            if last_build_status:
                pytest.skip("Test job {0} is already running").format(jenkins_test_job)
        #This jenkins module doesn't work with build_job function without parameters
        #Just send some fake parameters. All others will be used from default values
        param_dict = {'foo':'bar'}
        server.build_job(jenkins_test_job, param_dict)
        timeout = 0
        #Use job status True by default to exclude timeout between build job and start job.
        job_status = True
        while job_status and ( timeout < 180 ):
            time.sleep(10)
            timeout += 10
            job_status = server.get_build_info(jenkins_test_job,next_build_num)['building']
        job_result = server.get_build_info(jenkins_test_job,next_build_num)['result']
    else:
        pytest.skip("The job {0} was not found").format(test_job_name)
    assert job_result == 'SUCCESS', \
        '''Test job '{0}' build was not successfull or timeout is too small
         '''.format(jenkins_test_job)

def test_drivetrain_services_replicas(local_salt_client):
    salt_output = local_salt_client.cmd(
        'I@gerrit:client',
        'cmd.run',
        ['docker service ls'],
        expr_form='compound')
    wrong_items = []
    for line in salt_output[salt_output.keys()[0]].split('\n'):
        if line[line.find('/') - 1] != line[line.find('/') + 1] \
           and 'replicated' in line:
            wrong_items.append(line)
    assert len(wrong_items) == 0, \
        '''Some DriveTrain services doesn't have expected number of replicas:
              {}'''.format(json.dumps(wrong_items, indent=4))


def test_drivetrain_components_and_versions(local_salt_client):
    config = utils.get_configuration()
    version = config['drivetrain_version'] or []
    if not version or version == '':
        pytest.skip("drivetrain_version is not defined. Skipping")
    salt_output = local_salt_client.cmd(
        'I@gerrit:client',
        'cmd.run',
        ['docker service ls'],
        expr_form='compound')
    not_found_services = ['gerrit_db', 'gerrit_server', 'jenkins_master',
                          'jenkins_slave01', 'jenkins_slave02',
                          'jenkins_slave03', 'ldap_admin', 'ldap_server']
    version_mismatch = []
    for line in salt_output[salt_output.keys()[0]].split('\n'):
        for service in not_found_services:
            if service in line:
                not_found_services.remove(service)
                if version != line.split()[4].split(':')[1]:
                    version_mismatch.append("{0}: expected "
                        "version is {1}, actual - {2}".format(service,version,
                                                              line.split()[4].split(':')[1]))
                continue
    assert len(not_found_services) == 0, \
        '''Some DriveTrain components are not found:
              {}'''.format(json.dumps(not_found_services, indent=4))
    assert len(version_mismatch) == 0, \
        '''Version mismatch found:
              {}'''.format(json.dumps(version_mismatch, indent=4))


def test_jenkins_jobs_branch(local_salt_client):
    config = utils.get_configuration()
    expected_version = config['drivetrain_version'] or []
    if not expected_version or expected_version == '':
        pytest.skip("drivetrain_version is not defined. Skipping")
    jenkins_password = get_password(local_salt_client,'jenkins:client')
    version_mismatch = []
    server = join_to_jenkins(local_salt_client,'admin',jenkins_password)
    for job_instance in server.get_jobs():
        job_name = job_instance.get('name')
        job_config = server.get_job_config(job_name)
        xml_data = minidom.parseString(job_config)
        BranchSpec = xml_data.getElementsByTagName('hudson.plugins.git.BranchSpec')
        #We use master branch for pipeline-library in case of 'testing,stable,nighlty' versions
        if expected_version in ['testing','nightly','stable']:
            expected_version = 'master'
        if BranchSpec:
            actual_version = BranchSpec[0].getElementsByTagName('name')[0].childNodes[0].data
            if ( actual_version != expected_version ) and ( job_name not in ['cvp-func','cvp-ha','cvp-perf'] ) :
                version_mismatch.append("Job {0} has {1} branch."
                                        "Expected {2}".format(job_name,
                                                              actual_version,
                                                              expected_version))
    assert len(version_mismatch) == 0, \
        '''Some DriveTrain jobs have version/branch mismatch:
              {}'''.format(json.dumps(version_mismatch, indent=4))
