from consumer import PowerConsumerDummy, JSONRPCServer
import netifaces as ni
import gevent

DEFAULT_INTERFACE_NAME = 'eth0'
RPCPort = 4040

def main():
    app = PowerConsumerDummy()
    ni.ifaddresses(DEFAULT_INTERFACE_NAME)
    host = ni.ifaddresses(DEFAULT_INTERFACE_NAME)[2][0]['addr']
    print host
    rpc_server = JSONRPCServer(app, '127.0.0.1', RPCPort)
    rpc_server.start()
    # while not app.consumer_ready:
    #     print 'Waiting for RPC calls!'
    #     gevent.sleep(1)
    # app.run()


if __name__ == '__main__':
    main()

    # For raspberry:
    # sudo apt-get install build-essential automake pkg-config libtool libffi-dev libgmp-dev libssl-dev
    # install solidity:


# TODO: exlude all solc dependend stuff
