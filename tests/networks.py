import ctypes
import subprocess


CLONE_NEWNET = 0x40000000  # The namespace type for network namespaces


class NetworkNamespace:

    def __enter__(self):
        stdout, _ = self.run_command(f'ip netns list | grep -wc "{self.name}" || true')
        if stdout == "1":
            self.__exit__(None, None, None)
        self.run_command(f'ip netns add {self.name}', with_ns=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.run_command(f'ip netns delete {self.name}', with_ns=False)

    @property
    def name(self):
        return self.__class__.__name__

    def file(self):
        return f'/var/run/netns/{self.name}'

    def run_command(self, cmd, with_ns=True):
        try:
            if with_ns:
                cmd = f'ip netns exec {self.name} {cmd}'
            process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return process.stdout.decode().strip(), process.stderr.decode().strip()
        except subprocess.CalledProcessError as e:
            print(f'Error running command: {cmd}')
            print(f'Error: {e}')
            print(f'Stdout: {e.stdout.decode()}')
            print(f'Stderr: {e.stderr.decode()}')
            raise

    def summary(self):
        # TODO - return dict of values
        print(f'Summary for {self.name}')
        print('================')

        for command in ['ip -br link show', 'ip -br addr show', 'ip -br neigh show', 'ip -br route show']:
            stdout, _ = self.run_command(f'ip netns exec {self.name} {command}')
            print(f'\n{command.split()[-2].capitalize()}:\n{stdout}')


class BasicNamespace(NetworkNamespace):

    def __enter__(self):
        super().__enter__()

        for dev in ['a1', 'a2', 'a3']:
            self.run_command(f'ip link add {dev} type dummy')
            self.run_command(f'ip link set {dev} up')
            self.run_command(f'ip link set {dev} multicast on')

        self.run_command('ip addr add 10.0.0.1/24 dev a1')
        self.run_command('ip addr add 20.0.0.1/24 dev a2')
        self.run_command('ip addr add 30.0.0.1/24 dev a3')
        self.run_command('ip link set lo up')
        return self


# Set network namespace
def setns(netns_path):
    libc = ctypes.CDLL('libc.so.6')

    with open(netns_path, 'r') as netns_file:
        # The second argument is the namespace type.
        result = libc.setns(netns_file.fileno(), CLONE_NEWNET)

    if result == -1:
        raise OSError(ctypes.get_errno())


def setup_veth_pair(namespace: NetworkNamespace):
    # setup veth pair for REST API access
    namespace.run_command('ip link add veth0 type veth peer name veth1', with_ns=False)
    namespace.run_command(f'ip link set veth1 netns {namespace.name}', with_ns=False)
    namespace.run_command('ip addr add 172.20.0.1/24 dev veth0', with_ns=False)
    namespace.run_command('ip link set veth0 up', with_ns=False)
    namespace.run_command('ip addr add 172.20.0.2/24 dev veth1')
    namespace.run_command('ip link set veth1 up')

    namespace.run_command('iptables -t nat -A PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 172.20.0.2:8000', with_ns=False)
    namespace.run_command('iptables -t nat -A POSTROUTING -p tcp --sport 8000 -j MASQUERADE')


def teardown_veth_pair(namespace: NetworkNamespace):
    namespace.run_command('iptables -t nat -D PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 172.20.0.2:8000', with_ns=False)
    namespace.run_command('ip link del veth0', with_ns=False)

