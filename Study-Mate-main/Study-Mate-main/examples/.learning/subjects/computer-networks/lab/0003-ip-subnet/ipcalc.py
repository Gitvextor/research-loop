"""第 3 课 lab · 子网计算器（任务留白态）。

把下面每个函数的实现补上，再跑测试：

    cd lab/0003-ip-subnet
    python3 -m unittest -v

规则只有一条：**不许 import ipaddress**——这个模块存在的意义就是把位运算亲手写一遍。
`ipaddress` 只出现在测试里，用来当对照答案。

任务与卡壳顺序见 ../README.md。
"""


def ip_to_int(text):
    """把点分十进制地址转成 32 位整数（T1）。

    >>> ip_to_int("192.168.1.100")
    3232235876
    >>> ip_to_int("0.0.0.0")
    0

    四组数字，每组取值 0~255；组数不对或某组不是十进制数字时抛 ValueError。
    """
    raise NotImplementedError("T1：先拆出四组数字，再把它们拼成一个整数")


def int_to_ip(value):
    """把 32 位整数转回点分十进制（T1）。

    >>> int_to_ip(3232235876)
    '192.168.1.100'

    value 超出 0 ~ 4294967295 时抛 ValueError。
    """
    raise NotImplementedError("T1：把 32 位按 8 位一组切出来")


def parse_cidr(text):
    """把 "地址/前缀长度" 拆成 (地址, 前缀长度)（T2）。

    >>> parse_cidr("192.168.1.100/26")
    ('192.168.1.100', 26)

    没有斜杠、前缀不是 0~32 的整数、地址本身不合法，都抛 ValueError。
    """
    raise NotImplementedError("T2：在斜杠处切开，两半都要校验")


def network_of(cidr):
    """网络地址：主机位全部清零（T3）。

    >>> network_of("192.168.1.100/26")
    '192.168.1.64'
    """
    raise NotImplementedError("T3：先写出掩码，再做按位与")


def broadcast_of(cidr):
    """广播地址：主机位全部置 1（T3）。

    >>> broadcast_of("192.168.1.100/26")
    '192.168.1.127'
    """
    raise NotImplementedError("T3：网络地址不动，把主机位全填成 1")


def host_count(prefix):
    """这个前缀长度下可分配给主机的地址个数（T3）。

    >>> host_count(26)
    62
    >>> host_count(31)
    2
    >>> host_count(32)
    1

    地址总数大于 2 时减掉网络地址与广播地址；/31 与 /32 是例外，见 T4。
    """
    raise NotImplementedError("T3：先算地址总数 2 ** (32 - prefix)，再决定减不减 2")


def usable_range(cidr):
    """可分配地址的首尾（T4）。

    >>> usable_range("192.168.1.100/26")
    ('192.168.1.65', '192.168.1.126')
    >>> usable_range("10.0.0.0/31")
    ('10.0.0.0', '10.0.0.1')
    >>> usable_range("10.0.0.7/32")
    ('10.0.0.7', '10.0.0.7')

    /31 与 /32 按 RFC 3021 处理：地址总数不大于 2 时两头都不去掉。
    """
    raise NotImplementedError("T4：先把地址总数算出来，再按 1 / 2 / 更多分三种情况处理")


def same_subnet(a, b):
    """两个带前缀长度的地址是否属于同一个网段（T5）。

    >>> same_subnet("192.168.1.65/26", "192.168.1.126/26")
    True
    >>> same_subnet("192.168.1.100/26", "192.168.1.130/26")
    False

    两个地址的前缀长度必须一致，否则抛 ValueError。
    """
    raise NotImplementedError("T5：分别求网络地址再比较")


def split(cidr, new_prefix):
    """把一个网段切成等长的子网，返回子网的 CIDR 字符串列表（T5）。

    >>> split("192.168.1.0/24", 26)
    ['192.168.1.0/26', '192.168.1.64/26', '192.168.1.128/26', '192.168.1.192/26']

    new_prefix 必须不小于原来的前缀，也不能大于 32，否则抛 ValueError。
    """
    raise NotImplementedError("T5：算出步长与块数，循环生成")
