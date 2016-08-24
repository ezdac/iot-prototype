import os

import gevent

import gevent.monkey
from ethereum.keys import privtoaddr, PBKDF2_CONSTANTS
from ethereum._solidity import compile_file
from raiden.utils import sha3
from raiden.tests.utils.tests import cleanup_tasks
from raiden.network.transport import UDPTransport
from raiden.network.rpc.client import (
    patch_send_transaction,
    BlockChainService,
    BlockChainServiceMock,
    DEFAULT_POLL_TIMEOUT,
    GAS_LIMIT,
    MOCK_REGISTRY_ADDRESS,
)
from pyethapp.rpc_client import JSONRPCClient
from raiden.blockchain.abi import get_contract_path
from raiden.raiden_service import DEFAULT_SETTLE_TIMEOUT
from raiden.network.discovery import ContractDiscovery
from raiden.tests.utils.network import (
    create_network,
    create_sequential_network,
    create_hydrachain_cluster,
    create_geth_cluster,
    CHAIN,
    DEFAULT_DEPOSIT,
)


def deploy_default_config():
    path = os.path.join(os.getcwd(), 'tmpgeth')
    resource_dict = genesis_geth_node(path)
    assert len(resource_dict['geth_processes']) == 1
    # XXX syncing problem? shouldn't it be:
    #   1) boostrap local blockchain (miner thread!)
    #   2) sync remote geth (non miner?)
    #   3) deploy contracts, initialise local raiden app
    #   4) initialise remote raiden app with registry, discovery, privkey from 3)
    private_keys = resource_dict['private_keys']
    resource_dict.update(deploy_network(private_keys))
    return resource_dict


def genesis_geth_node(tmpdir,
                        cluster_number_of_nodes=2,
                        cluster_key_seed='cluster:{}',
                        number_of_nodes=2,
                        privatekey_seed='key:{}',
                        p2p_base_port=29870,
                        ):
    cluster_unassigned_private_keys = [
        sha3(cluster_key_seed.format(position))
        for position in range(cluster_number_of_nodes)
    ]

    private_keys = [
        sha3(privatekey_seed.format(position))
        for position in range(number_of_nodes)
    ]

    cluster_private_keys = [cluster_unassigned_private_keys.pop(1)]

    geth_processes = create_geth_cluster(
        private_keys,
        cluster_private_keys,
        p2p_base_port,
        str(tmpdir),
    )
    return {'geth_processes': geth_processes,
            'private_keys': private_keys,
            'geth_private_keys': cluster_private_keys,
            'geth_unassigned_private_keys': cluster_unassigned_private_keys}

def deploy_network(private_keys, channels_per_node=1, deposit=DEFAULT_DEPOSIT,
                     number_of_assets=1, settle_timeout=DEFAULT_SETTLE_TIMEOUT,
                     poll_timeout=DEFAULT_POLL_TIMEOUT,transport_class=UDPTransport
                     ):

    gevent.sleep(2)
    # assert channels_per_node in (0, 1, 2, CHAIN), (
    #     'deployed_network uses create_sequential_network that can only work '
    #     'with 0, 1 or 2 channels'
    #

    privatekey = private_keys[0]
    address = privtoaddr(privatekey)
    blockchain_service_class = BlockChainService

    jsonrpc_client = JSONRPCClient(
        host='0.0.0.0',
        # port=4000, #XXX modified
        privkey=privatekey,
        print_communication=True, #XXX modified
    )
    patch_send_transaction(jsonrpc_client)

    humantoken_path = get_contract_path('HumanStandardToken.sol')
    registry_path = get_contract_path('Registry.sol')

    humantoken_contracts = compile_file(humantoken_path, libraries=dict())
    registry_contracts = compile_file(registry_path, libraries=dict())

    registry_proxy = jsonrpc_client.deploy_solidity_contract(
        address,
        'Registry',
        registry_contracts,
        dict(),
        tuple(),
        timeout=poll_timeout,
    )
    registry_address = registry_proxy.address

    # Using 3 * deposit because we assume that is the maximum number of
    # channels that willbe created.
    # `total_per_node = channels_per_node * deposit`
    total_per_node = 3 * deposit
    total_asset = total_per_node * len(private_keys)
    asset_addresses = []
    for _ in range(number_of_assets):
        token_proxy = jsonrpc_client.deploy_solidity_contract(
            address,
            'HumanStandardToken',
            humantoken_contracts,
            dict(),
            (total_asset, 'raiden', 2, 'Rd'),
            timeout=poll_timeout,
        )
        asset_address = token_proxy.address
        assert len(asset_address)
        asset_addresses.append(asset_address)

        transaction_hash = registry_proxy.addAsset(asset_address)  # pylint: disable=no-member
        jsonrpc_client.poll(transaction_hash.decode('hex'), timeout=poll_timeout)

        # only the creator of the token starts with a balance, transfer from
        # the creator to the other nodes
        for transfer_to in private_keys:
            if transfer_to != jsonrpc_client.privkey:
                transaction_hash = token_proxy.transfer(  # pylint: disable=no-member
                    privtoaddr(transfer_to),
                    total_per_node,
                    startgas=GAS_LIMIT,
                )
                jsonrpc_client.poll(transaction_hash.decode('hex'))

        for key in private_keys:
            assert token_proxy.balanceOf(privtoaddr(key)) == total_per_node  # pylint: disable=no-member

        discovery_contract_path = get_contract_path('EndpointRegistry.sol')
        discovery_contracts = compile_file(discovery_contract_path, libraries=dict())
        discovery_contract_proxy = jsonrpc_client.deploy_solidity_contract(
            address,
            'EndpointRegistry',
            discovery_contracts,
            dict(),
            tuple(),
            timeout=poll_timeout,
        )
        discovery_contract_address = discovery_contract_proxy.address
        # initialize and return ContractDiscovery object
        #  ContractDiscovery(jsonrpc_client, discovery_contract_address)

        raiden_apps = create_sequential_network(
            private_keys,
            asset_addresses[0],
            registry_address,
            channels_per_node,
            deposit,
            settle_timeout,
            poll_timeout,
            transport_class,
            blockchain_service_class,
        )

        return {
            'raiden_apps': raiden_apps,
            'asset_address': asset_addresses[0],
            'registry_address': registry_address,
            'discovery_address': discovery_contract_address
        }

if __name__ == '__main__':
    app1, app2 = deploy_default_config()
    app1_address = app1.raiden.api.address
    app2_address = app2.raiden.api.address
    asset_address = app1.raiden.api.assets[0]
    assert asset_address == app2.raiden.api.assets[0]
