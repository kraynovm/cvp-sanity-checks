import pytest
import cvp_checks.utils as utils


@pytest.fixture(scope='session')
def local_salt_client():
    return utils.init_salt_client()

nodes = utils.calculate_groups()


@pytest.fixture(scope='session', params=nodes.values(), ids=nodes.keys())
def nodes_in_group(request):
    return request.param


@pytest.fixture(scope='session')
def check_prometheus(local_salt_client):
    salt_output = local_salt_client.cmd(
        'prometheus:server',
        'test.ping',
        expr_form='pillar')
    if not salt_output:
        pytest.skip("Prometheus service or prometheus:server pillar \
          are not found on this environment.")


@pytest.fixture(scope='session')
def check_kibana(local_salt_client):
    salt_output = local_salt_client.cmd(
        'kibana:server',
        'test.ping',
        expr_form='pillar')
    if not salt_output:
        pytest.skip("Kibana service or kibana:server pillar \
          are not found on this environment.")


@pytest.fixture(scope='session')
def check_grafana(local_salt_client):
    salt_output = local_salt_client.cmd(
        'grafana:client',
        'test.ping',
        expr_form='pillar')
    if not salt_output:
        pytest.skip("Grafana service or grafana:client pillar \
          are not found on this environment.")


def pytest_namespace():
    return {'contrail': None}


@pytest.fixture(scope='module')
def contrail(local_salt_client):
    probe = local_salt_client.cmd(
        'opencontrail:control',
        'pillar.get',
        'opencontrail:control:version',
        expr_form='pillar')
    if not probe:
        pytest.skip("Contrail is not found on this environment")
    versions = set(probe.values())
    if len(versions) != 1:
        pytest.fail('Contrail versions are not the same: {}'.format(probe))
    pytest.contrail = str(versions.pop())[:1]
