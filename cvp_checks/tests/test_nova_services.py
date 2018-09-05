import pytest


def test_nova_services_status(local_salt_client):
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['. /root/keystonerc; nova service-list | grep "down\|disabled" | grep -v "Forced down"'],
        expr_form='pillar')

    if not result:
        pytest.skip("Nova service or keystone:server pillar \
        are not found on this environment.")

    assert result[result.keys()[0]] == '', \
        '''Some nova services are in wrong state'''
