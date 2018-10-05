import os
import yaml
import requests
import re
import sys, traceback


class AuthenticationError(Exception):
    pass


class salt_remote:
    def cmd(self, tgt, fun, param=None, expr_form=None, tgt_type=None):
        config = get_configuration()
        url = config['SALT_URL'].strip()
        if not re.match("^(http|https)://", url):
            raise AuthenticationError("Salt URL should start \
            with http or https, given - {}".format(url))
        proxies = {"http": None, "https": None}
        headers = {'Accept': 'application/json'}
        login_payload = {'username': config['SALT_USERNAME'],
                         'password': config['SALT_PASSWORD'], 'eauth': 'pam'}
        accept_key_payload = {'fun': fun, 'tgt': tgt, 'client': 'local',
                              'expr_form': expr_form, 'tgt_type': tgt_type,
                              'timeout': config['salt_timeout']}
        if param:
            accept_key_payload['arg'] = param

        try:
            login_request = requests.post(os.path.join(url, 'login'),
                                          headers=headers, data=login_payload,
                                          proxies=proxies)
            if not login_request.ok:
                raise AuthenticationError("Authentication to SaltMaster failed")

            request = requests.post(url, headers=headers,
                                    data=accept_key_payload,
                                    cookies=login_request.cookies,
                                    proxies=proxies)

            response = request.json()['return'][0]
            not_responded = [k for k,v in response.iteritems() if v is False]
            if not_responded:
                print ("WARNING: Some nodes are unavailable and removed "
                      "from response: {}".format(', '.join(not_responded))
                )
            for node in not_responded:
                del response[node]
            return response

        except Exception as e:
            print ("\033[91m\nConnection to SaltMaster "
                  "was not established.\n"
                  "Please make sure that you "
                  "provided correct credentials.\n"
                  "Error message: {}\033[0m\n".format(e.message or e)
            )
            traceback.print_exc(file=sys.stdout)
            sys.exit()


def init_salt_client():
    local = salt_remote()
    return local


def list_to_target_string(node_list, separator, add_spaces=True):
    if add_spaces:
        separator = ' ' + separator.strip() + ' '
    return separator.join(node_list)


def get_monitoring_ip(param_name):
    local_salt_client = init_salt_client()
    salt_output = local_salt_client.cmd(
        'salt:master',
        'pillar.get',
        ['_param:{}'.format(param_name)],
        expr_form='pillar')
    return salt_output[salt_output.keys()[0]]


def get_active_nodes(test=None):
    config = get_configuration()
    local_salt_client = init_salt_client()

    skipped_nodes = config.get('skipped_nodes') or []
    if test:
        testname = test.split('.')[0]
        if 'skipped_nodes' in config.get(testname).keys():
            skipped_nodes += config.get(testname)['skipped_nodes'] or []
    if skipped_nodes != ['']:
        print "\nNotice: {0} nodes will be skipped".format(skipped_nodes)
        nodes = local_salt_client.cmd(
            '* and not ' + list_to_target_string(skipped_nodes, 'and not'),
            'test.ping',
            expr_form='compound')
    else:
        nodes = local_salt_client.cmd('*', 'test.ping')
    return nodes


def calculate_groups():
    config = get_configuration()
    local_salt_client = init_salt_client()
    node_groups = {}
    nodes_names = set ()
    expr_form = ''
    all_nodes = set(local_salt_client.cmd('*', 'test.ping'))
    if 'groups' in config.keys() and 'PB_GROUPS' in os.environ.keys() and \
       os.environ['PB_GROUPS'].lower() != 'false':
        nodes_names.update(config['groups'].keys())
        expr_form = 'compound'
    else:
        for node in all_nodes:
            index = re.search('[0-9]{1,3}$', node.split('.')[0])
            if index:
                nodes_names.add(node.split('.')[0][:-len(index.group(0))])
            else:
                nodes_names.add(node)
        expr_form = 'pcre'

    gluster_nodes = local_salt_client.cmd('I@salt:control and '
                                          'I@glusterfs:server',
                                          'test.ping', expr_form='compound')
    kvm_nodes = local_salt_client.cmd('I@salt:control and not '
                                      'I@glusterfs:server',
                                      'test.ping', expr_form='compound')

    for node_name in nodes_names:
        skipped_groups = config.get('skipped_groups') or []
        if node_name in skipped_groups:
            continue
        if expr_form == 'pcre':
            nodes = local_salt_client.cmd('{}[0-9]{{1,3}}'.format(node_name),
                                          'test.ping',
                                          expr_form=expr_form)
        else:
            nodes = local_salt_client.cmd(config['groups'][node_name],
                                          'test.ping',
                                          expr_form=expr_form)
            if nodes == {}:
                continue

        node_groups[node_name]=[x for x in nodes
                                if x not in config['skipped_nodes']
                                if x not in gluster_nodes.keys()
                                if x not in kvm_nodes.keys()]
        all_nodes = set(all_nodes - set(node_groups[node_name]))
        if node_groups[node_name] == []:
            del node_groups[node_name]
            if kvm_nodes:
                node_groups['kvm'] = kvm_nodes.keys()
            node_groups['kvm_gluster'] = gluster_nodes.keys()
    all_nodes = set(all_nodes - set(kvm_nodes.keys()))
    all_nodes = set(all_nodes - set(gluster_nodes.keys()))
    if all_nodes:
        print ("These nodes were not collected {0}. Check config (groups section)".format(all_nodes))
    return node_groups
                
            
def get_configuration():
    """function returns configuration for environment
    and for test if it's specified"""
    global_config_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../global_config.yaml")
    with open(global_config_file, 'r') as file:
        global_config = yaml.load(file)
    for param in global_config.keys():
        if param in os.environ.keys():
            if ',' in os.environ[param]:
                global_config[param] = []
                for item in os.environ[param].split(','):
                    global_config[param].append(item)
            else:
                global_config[param] = os.environ[param]

    return global_config
