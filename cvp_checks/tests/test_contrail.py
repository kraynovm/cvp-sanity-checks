import pytest
import json

pytestmark = pytest.mark.usefixtures("contrail")

STATUS_FILTER = r'grep -Pv "(==|^$|Disk|unix|support|boot|\*\*|FOR NODE)"'
STATUS_COMMAND = "contrail-status -t 10"

def get_contrail_status(salt_client, pillar, command, processor):
    return salt_client.cmd(
        pillar, 'cmd.run',
        ['{} | {}'.format(command, processor)],
        expr_form='pillar'
    )

def test_contrail_compute_status(local_salt_client):
    cs = get_contrail_status(local_salt_client, 'nova:compute',
                             STATUS_COMMAND, STATUS_FILTER)
    broken_services = []

    for node in cs:
        for line in cs[node].split('\n'):
            line = line.strip()
            if len (line.split(None, 1)) == 1:
                err_msg = "{0}: {1}".format(
                    node, line)
                broken_services.append(err_msg)
                continue
            name, status = line.split(None, 1)
            if status not in {'active'}:
                err_msg = "{node}:{service} - {status}".format(
                    node=node, service=name, status=status)
                broken_services.append(err_msg)

    assert not broken_services, 'Broken services: {}'.format(json.dumps(
                                                             broken_services,
                                                             indent=4))


def test_contrail_node_status(local_salt_client):
    command = STATUS_COMMAND

    # TODO: what will be in OpenContrail 5?
    if pytest.contrail == '4':
        command = "doctrail all " + command
    cs = get_contrail_status(local_salt_client,
                             'opencontrail:client:analytics_node',
                             command, STATUS_FILTER)
    cs.update(get_contrail_status(local_salt_client, 'opencontrail:control',
                                  command, STATUS_FILTER)
    )
    broken_services = []
    for node in cs:
        for line in cs[node].split('\n'):
            line = line.strip()
            if 'crashes/core.java.' not in line:
                name, status = line.split(None, 1)
            else:
                name, status = line, 'FATAL'
            if status not in {'active', 'backup'}:
                err_msg = "{node}:{service} - {status}".format(
                    node=node, service=name, status=status)
                broken_services.append(err_msg)

    assert not broken_services, 'Broken services: {}'.format(json.dumps(
                                                             broken_services,
                                                             indent=4))


def test_contrail_vrouter_count(local_salt_client):
    cs = get_contrail_status(local_salt_client, 'nova:compute',
                             STATUS_COMMAND, STATUS_FILTER)

    # TODO: what if compute lacks these service unintentionally?
    if not cs:
        pytest.skip("Contrail services were not found on compute nodes")

    actual_vrouter_count = 0
    for node in cs:
        for line in cs[node].split('\n'):
            if 'contrail-vrouter-nodemgr' in line:
                actual_vrouter_count += 1

    assert actual_vrouter_count == len(cs.keys()),\
        'The length of vRouters {} differs' \
        ' from the length of compute nodes {}'.format(actual_vrouter_count,
                                                      len(cs.keys()))
