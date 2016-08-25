import sys
# import os
# sys.path.append(os.path(os.getcwd))
# print sys.path
# print __name__
from vendor_nondaemon import PowerMeterDummy, ConsumerProxy
# import vendor_nondaemon
from utils.network import deploy_default_config
import netifaces as ni
from raiden.utils import privtoaddr

DEFAULT_INTERFACE_NAME = 'wlp3s0'

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
    print consumer_proxy.__dict__
    consumer_proxy.remote_start_geth_node(
        [key.encode('hex') for key in private_keys],
        # geth_private_key=geth_remote_private_key,
        deployed_network['geth_private_keys'][0].encode('hex'),
        29870,
        bootstrap_enode)
    deployed_network['geth_private_keys'].append(geth_remote_private_key)

    registry_address = deployed_network['registry_address']
    discovery_address = deployed_network['discovery_address']
    asset_address = deployed_network['asset_address']

    consumer_proxy.remote_start_raiden_app(
        discovery=discovery_address,
        registry=registry_address
    )

    #TODO: get addresses
    pm = PowerMeterDummy(raiden=deploy_network['raiden_apps'][0], # XXX check for correct app
        consumer_proxy=consumer_proxy,
        initial_price=4000,
        asset_address=asset_address,
        partner_address=privtoaddr(private_keys[1]) #XXX check
    )

    pm.run()



if __name__ == '__main__':
    consumer_host, consumer_port = sys.argv[1:]
    main(consumer_host, consumer_port)
