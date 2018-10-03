import jenkins
from xml.dom import minidom
from cvp_checks import utils
import json
import pytest
from time import sleep

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

def test_drivetrain_jenkins_job(local_salt_client):
    jenkins_password = local_salt_client.cmd(
        'jenkins:client',
        'pillar.get',
        ['_param:openldap_admin_password'],
        expr_form='pillar').values()[0]
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
            sleep(10)
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
    jenkins_password = local_salt_client.cmd(
        'jenkins:client',
        'pillar.get',
        ['_param:openldap_admin_password'],
        expr_form='pillar').values()[0]
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
