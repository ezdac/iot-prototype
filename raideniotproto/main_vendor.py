import sys
import os
import json
import time
import copy
from raiden.app import app
# import os
# sys.path.append(os.path(os.getcwd))
# print sys.path
# print __name__
from vendor_nondaemon import PowerMeterRaspberry
# # import vendor_nondaem
# from utils.network import deploy_default_config
# import netifaces as ni
# from raiden.utils import privtoaddr
#
# DEFAULT_INTERFACE_NAME = 'wlp3s0'

def main(consumer_host, consumer_port):

    ni.ifaddresses(DEFAULT_INTERFACE_NAME)
    host = ni.ifaddresses(DEFAULT_INTERFACE_NAME)[2][0]['addr']

    deployed_network = deploy_default_config()
    print deployed_network
    geth_private_keys = deployed_network['geth_private_keys'] # XXX make shure first one is bootstrap
    bootstrap_enode = 'enode://{pub}@{host}:{port}'.format(
        pub=privtoaddr(geth_private_keys[0]).encode('hex'), #XXX check encoding
        host=host,
        port=29870 #XXX check
    )
    print bootstrap_enode,
    private_keys = deployed_network['private_keys']
    geth_remote_private_key= deployed_network['geth_unassigned_private_keys'].pop()
    consumer_proxy = ConsumerProxy(consumer_host, consumer_port).rpc_proxy
    private_keys_encoded = [key.encode('hex') for key in private_keys]
    geth_remote_private_key_encoded = geth_remote_private_key.encode('hex')
    print private_keys_encoded
    time.sleep(10000)
    consumer_proxy.remote_start_geth_node(
        private_keys_encoded,
        geth_remote_private_key_encoded,
        '29870',
        bootstrap_enode)
    # consumer_proxy.remote_start_geth_node(
    #     ['1','2'],
    #     '1',
    #     29870,
    #     '1')
    deployed_network['geth_private_keys'].append(geth_remote_private_key)

    registry_address = deployed_network['registry_address'].encode('hex')
    discovery_address = deployed_network['discovery_address'].encode('hex')
    asset_address = deployed_network['asset_address'].encode('hex')

    time.sleep(10000)

    consumer_proxy.remote_start_raiden_app(
        discovery_address,
        registry_address
    )

    #TODO: get addresses
    pm = PowerMeterDummy(raiden=deploy_network['raiden_apps'][0], # XXX check for correct app
        consumer_proxy=consumer_proxy,
        initial_price=4000,
        asset_address=asset_address.decode('hex'),
        partner_address=privtoaddr(private_keys[1]) #XXX check
    )

    pm.run()

DEFAULT_ETH_RPC_ENDPOINT = '192.168.0.77:8545'


def main_new(config_dir):
    # files = ['raiden_accounts.json', 'scenario.json', 'genesis.json']
    # dicts = dict()
    # for file in files:
    #     name = copy.deepcopy(file)
    #     file = os.path.join(os.path.abspath(config_dir), file)
    #     with open(file, 'r') as f:
    #         dump = json.load(f)
    #         dicts[name] = dump
    #
    # # --rpc_endpoint "192.168.0.77:8545"
    # flags = dicts['genesis.json']['config']['raidenFlags'].split('--')
    # print flags
    # print dicts['raiden_accounts.json']

    privatekey = 'c85e103f2b2de251d9af35feb3e9979a8a9109f4bf66d087b200d2ab43d933df'
    registry_contract_address = '4fb87c52b194f78cd4896e3e574028fedbab9'
    discovery_contract_address = 'ed8d61f42dc1e56ae992d333a4992c3796b22a74'
    token_address = "ae519fc2ba8e6ffe6473195c092bf1bae986ff90"

    app = make_app(privatekey, DEFAULT_ETH_RPC_ENDPOINT, registry_contract_address,
        discovery_contract_address)
    # register token once
    app.raiden.chain.default_registry.add_asset(token_address)
    # register adress - endpoint
    app.discovery.register(app.raiden.address, '192.168.0.118', '40001')
    # wait for receiving address:
    partner = None
    while not partner:
        partner = app.discovery.nodeid_by_host_port(('192.168.0.139', '40001'))
        gevent.sleep(1)

    # obtain channel address!?
    powermeter = PowerMeterRaspberry(app.raiden, initial_price=1, token_address, partner)
    powermete.run()



def make_app(privatekey, eth_rpc_endpoint, registry_contract_address,
        discovery_contract_address):

    slogging.configure(logging, log_file=logfile)

    if not external_listen_address:
        # notify('if you are behind a NAT, you should set
        # `external_listen_address` and configure port forwarding on your router')
        external_listen_address = listen_address

    # config_file = args.config_file
    (listen_host, listen_port) = split_endpoint(listen_address)

    config = App.default_config.copy()
    config['host'] = listen_host
    config['port'] = listen_port
    config['privatekey_hex'] = privatekey

    endpoint = eth_rpc_endpoint

    if eth_rpc_endpoint.startswith("http://"):
        endpoint = eth_rpc_endpoint[len("http://"):]
        rpc_port = 80
    elif eth_rpc_endpoint.startswith("https://"):
        endpoint = eth_rpc_endpoint[len("https://"):]
        rpc_port = 443

    if ':' not in endpoint:  # no port was given in url
        rpc_host = endpoint
    else:
        rpc_host, rpc_port = split_endpoint(endpoint)

    blockchain_service = BlockChainService(
        decode_hex(privatekey),
        decode_hex(registry_contract_address),
        host=rpc_host,
        port=rpc_port,
    )

    discovery = ContractDiscovery(
        blockchain_service,
        decode_hex(discovery_contract_address)  # FIXME: double encoding
    )

    app = App(config, blockchain_service, discovery)

    discovery.register(
        app.raiden.address,
        *split_endpoint(external_listen_address)
    )

    app.raiden.register_registry(blockchain_service.default_registry)

    return app

if __name__ == '__main__':
    #config_dir = sys.argv[1:]
    config_dir =os.environ['CONFIG_DIR']
    main_new()
