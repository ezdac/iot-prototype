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
    geth_private_keys = deployed_network['geth_private_keys'] # XXX make shure first one is bootstrap
    bootstrap_enode = 'enode://{pub}@{host}:{port}'.format(
        pub=privtoaddr(geth_private_keys[0]),
        host=host,
        port=29870 #XXX check
    )
    private_keys = deployed_network['private_keys']
    consumer_proxy = ConsumerProxy(consumer_host, consumer_port).rpc_proxy
    consumer_proxy.remote_start_geth_node(
        private_keys=private_keys,
        geth_private_key=geth_private_keys[1],
        p2p_base_port=29870,
        bootstrap_enode=bootstrap_enode)


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
