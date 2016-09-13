#import netifaces as ni
import gevent
from ethereum.utils import decode_hex

from raiden.raiden_service import RaidenService, DEFAULT_REVEAL_TIMEOUT, DEFAULT_SETTLE_TIMEOUT
from raiden.network.discovery import ContractDiscovery
from raiden.network.transport import UDPTransport
from raiden.network.rpc.client import BlockChainService
from raiden.app import App
from raiden.utils import pex, split_endpoint

from consumer import PowerConsumerRaspberry

from ethereum import slogging
slogging.configure(':INFO')

DEFAULT_INTERFACE_NAME = 'eth0'
RPCPort = 4040

def main():
    app = PowerConsumerDummy()
    print app.remote_start_geth_node.__dict__
    ni.ifaddresses(DEFAULT_INTERFACE_NAME)
    host = ni.ifaddresses(DEFAULT_INTERFACE_NAME)[2][0]['addr']
    print 'RPC-address:', host, RPCPort
    rpc_server = JSONRPCServer(app, '0.0.0.0', RPCPort)
    rpc_server.start()
    # while not app.consumer_ready:
    #     print 'Waiting for RPC calls!'
    #     gevent.sleep(1)
    # app.run()

DEFAULT_ETH_RPC_ENDPOINT = "192.168.0.72:8545"
DEFAULT_DEPOSIT_AMOUNT = 100

def main_new():
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

    privatekey = '3cfa276954f2f12a6d8ec0f1a2f13fa2ff3f7cf99f9eb8431a44ee41bc74d5f1'
    registry_contract_address = '4fb87c52bb6d194f78cd4896e3e574028fedbab9'
    discovery_contract_address = 'ed8d61f42dc1e56ae992d333a4992c3796b22a74'
    token_address = 'ae519fc2ba8e6ffe6473195c092bf1bae986ff90'
    app = make_app(privatekey, DEFAULT_ETH_RPC_ENDPOINT, registry_contract_address, discovery_contract_address,'0.0.0.0:40001', '192.168.0.139:40001')
    # wait for receiving address:
    partner = None
    while not partner:
        # check for JSONRPC errors XXX
        partner = app.discovery.nodeid_by_host_port(('192.168.0.118', '40001'))
        gevent.sleep(1)
    partner = partner.encode('hex')
    print partner
    # only open channel if not already opened XXX
    channel = None
    while not channel:
        try:
            channel = app.raiden.api.open(token_address, partner)
        except JSONRPCClientReplyError:
            continue

    # only deposit if not already deposited desired amount
    try:
        app.raiden.api.deposit(token_address, partner, amount=DEFAULT_DEPOSIT_AMOUNT)
    except Exception:
        print 'nothing deposited'
        pass
    powerconsumer = PowerConsumerRaspberry(app.raiden, 4000, token_address, partner, ui_server='http://192.168.0.72:8000')
    powerconsumer.run()


def make_app(privatekey, eth_rpc_endpoint, registry_contract_address,
        discovery_contract_address,listen_address,external_listen_address):

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
    main_new()

    # For raspberry:
    # sudo apt-get install build-essential automake pkg-config libtool libffi-dev libgmp-dev libssl-dev
    # install solidity:


# TODO: exlude all solc dependend stuff
