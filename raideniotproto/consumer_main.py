from consumer import PowerConsumerDummy, JSONRPCServer
import gevent

RPCPort = '4040'

def main():
    app = PowerConsumerDummy()
    rpc_server = JSONRPCServer(app, '127.0.0.1', RPCPort)
    rpc.server.start()
    while not app.consumer_ready:
        print 'Waiting for RPC calls!'
        gevent.sleep(1)
    app.run()


if __name__ == '__main__':
    main()
