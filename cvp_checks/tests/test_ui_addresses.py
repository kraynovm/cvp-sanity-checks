from cvp_checks import utils
import pytest


def test_ui_horizon(local_salt_client):
    salt_output = local_salt_client.cmd(
        'horizon:server',
        'pillar.get',
        ['_param:cluster_public_host'],
        expr_form='pillar')
    IP = [salt_output[node] for node in salt_output
          if salt_output[node]]
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['curl --insecure https://{}/auth/login/ 2>&1 | \
         grep Login'.format(IP[0])],
        expr_form='pillar')
    assert len(result[result.keys()[0]]) != 0, \
        'Horizon login page is not reachable on {} from ctl nodes'.format(
        IP[0])


def test_ui_kibana(local_salt_client):
    IP = utils.get_monitoring_ip('stacklight_log_address')
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['curl http://{}:5601/app/kibana 2>&1 | \
         grep loading'.format(IP)],
        expr_form='pillar')
    assert len(result[result.keys()[0]]) != 0, \
        'Kibana login page is not reachable on {} from ctl nodes'.format(IP)


def test_ui_prometheus(local_salt_client):
    IP = utils.get_monitoring_ip('stacklight_monitor_address')
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['curl http://{}:15010/graph 2>&1 | \
         grep Prometheus'.format(IP)],
        expr_form='pillar')
    assert len(result[result.keys()[0]]) != 0, \
        'Prometheus page is not reachable on {} from ctl nodes'.format(IP)


def test_ui_alert_manager(local_salt_client):
    IP = utils.get_monitoring_ip('stacklight_monitor_address')
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['curl -s http://{}:15011/ | grep Alertmanager'.format(IP)],
        expr_form='pillar')
    assert len(result[result.keys()[0]]) != 0, \
        'AlertManager page is not reachable on {} from ctl nodes'.format(IP)


def test_ui_grafana(local_salt_client):
    IP = utils.get_monitoring_ip('stacklight_monitor_address')
    result = local_salt_client.cmd(
        'keystone:server',
        'cmd.run',
        ['curl http://{}:15013/login 2>&1 | grep Grafana'.format(IP)],
        expr_form='pillar')
    assert len(result[result.keys()[0]]) != 0, \
        'Grafana page is not reachable on {} from ctl nodes'.format(IP)
