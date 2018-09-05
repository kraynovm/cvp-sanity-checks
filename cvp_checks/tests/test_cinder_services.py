import pytest


def test_cinder_services(local_salt_client):
    cinder_backends_info = local_salt_client.cmd(
        'cinder:controller',
        'pillar.get',
        ['cinder:controller:backend'],
        expr_form='pillar')
    if not cinder_backends_info:
        pytest.skip("Cinder service or cinder:controller pillar \
        are not found on this environment.")
    service_down = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['. /root/keystonerc; cinder service-list | grep "down\|disabled"'],
        expr_form='pillar')
    cinder_volume = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['. /root/keystonerc; cinder service-list | grep -c "volume"'],
        expr_form='pillar')
    backends_cinder = cinder_backends_info[cinder_backends_info.keys()[0]]
    backends_num = len(backends_cinder.keys())
    assert service_down[service_down.keys()[0]] == '', \
        '''Some cinder services are in wrong state'''
    assert cinder_volume[cinder_volume.keys()[0]] == str(backends_num), \
        'Number of cinder-volume services ({0}) does not match ' \
        'number of volume backends ({1})'.format(
        cinder_volume[cinder_volume.keys()[0]], str(backends_num))
