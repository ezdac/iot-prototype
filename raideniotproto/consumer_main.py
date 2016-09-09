from consumer import PowerConsumerDummy, JSONRPCServer
import netifaces as ni
import gevent

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

DEFAULT_ETH_RPC_ENDPOINT = "192.168.0.77:8545"
DEFAULT_DEPOSIT_AMOUNT = 100

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

    privatekey = '3cfa276954f2f12a6d8ec0f1a2f13fa2ff3f7cf99f9eb8431a44ee41bc74d5f1'
    registry_contract_address = '4fb87c52b194f78cd4896e3e574028fedbab9'
    discovery_contract_address = 'ed8d61f42dc1e56ae992d333a4992c3796b22a74'
    token_address = "ae519fc2ba8e6ffe6473195c092bf1bae986ff90"

    app = app(privatekey, DEFAULT_ETH_RPC_ENDPOINT, registry_contract_address,
        discovery_contract_address)
    # register token once
    # register adress - endpoint
    app.discovery.register(app.raiden.address, '192.168.0.139', '40001')
    # wait for receiving address:
    partner = None
    while not partner:
        partner = app.discovery.nodeid_by_host_port(('192.168.0.118', '40001'))
        gevent.sleep(1)
    #TODO: open channel, on consumer: deposit asset
    channel = app.raiden.api.open(token_address, partner)
    app.raiden.api.deposit(token_address, partner, amount=DEFAULT_DEPOSIT_AMOUNT)
    channel.address




if __name__ == '__main__':
    main_new()

    # For raspberry:
    # sudo apt-get install build-essential automake pkg-config libtool libffi-dev libgmp-dev libssl-dev
    # install solidity:


# TODO: exlude all solc dependend stuff
