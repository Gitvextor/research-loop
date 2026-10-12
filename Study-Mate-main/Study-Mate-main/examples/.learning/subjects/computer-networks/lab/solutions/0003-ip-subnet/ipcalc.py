"""第 3 课 lab · 子网计算器（参考解）。

只用位运算与内置函数，不 import ipaddress——对照答案由测试现算。
跟自己的实现比一比就行，测试全绿就算完成。
"""

FULL_MASK = 0xFFFFFFFF


def mask_of(prefix):
    """前缀长度 → 掩码：前 prefix 位是 1，其余是 0。"""
    if isinstance(prefix, bool) or not isinstance(prefix, int) or not 0 <= prefix <= 32:
        raise ValueError(f"前缀长度要写 0~32 的整数：{prefix!r}")
    return (FULL_MASK << (32 - prefix)) & FULL_MASK


def ip_to_int(text):
    """把点分十进制地址转成 32 位整数（T1）。

    >>> ip_to_int("192.168.1.100")
    3232235876
    """
    parts = str(text).split(".")
    if len(parts) != 4:
        raise ValueError(f"IPv4 地址要写成四组数字：{text!r}")
    value = 0
    for part in parts:
        if not (part.isascii() and part.isdigit()) or int(part) > 255:
            raise ValueError(f"每一组都要是 0~255 的十进制数字：{text!r}")
        value = (value << 8) | int(part)
    return value


def int_to_ip(value):
    """把 32 位整数转回点分十进制（T1）。

    >>> int_to_ip(3232235876)
    '192.168.1.100'
    """
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= FULL_MASK:
        raise ValueError(f"32 位整数要落在 0~{FULL_MASK} 之间：{value!r}")
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def parse_cidr(text):
    """把 "地址/前缀长度" 拆成 (地址, 前缀长度)（T2）。

    >>> parse_cidr("192.168.1.100/26")
    ('192.168.1.100', 26)
    """
    address, slash, prefix_text = str(text).partition("/")
    if not slash or not (prefix_text.isascii() and prefix_text.isdigit()):
        raise ValueError(f"要写成 地址/前缀长度，前缀是 0~32 的整数：{text!r}")
    prefix = int(prefix_text)
    if prefix > 32:
        raise ValueError(f"前缀长度要写 0~32 的整数：{text!r}")
    ip_to_int(address)          # 地址本身的合法性交给它校验
    return address, prefix


def network_of(cidr):
    """网络地址：IP 与掩码按位与，主机位清零（T3）。

    >>> network_of("192.168.1.100/26")
    '192.168.1.64'
    """
    address, prefix = parse_cidr(cidr)
    return int_to_ip(ip_to_int(address) & mask_of(prefix))


def broadcast_of(cidr):
    """广播地址：网络地址不动，主机位全部置 1（T3）。

    >>> broadcast_of("192.168.1.100/26")
    '192.168.1.127'
    """
    address, prefix = parse_cidr(cidr)
    host_mask = FULL_MASK >> prefix          # 主机位是 1、其余是 0
    return int_to_ip((ip_to_int(address) & mask_of(prefix)) | host_mask)


def host_count(prefix):
    """这个前缀长度下可分配给主机的地址个数（T3）。

    >>> host_count(26)
    62
    >>> host_count(31)
    2
    """
    if isinstance(prefix, bool) or not isinstance(prefix, int) or not 0 <= prefix <= 32:
        raise ValueError(f"前缀长度要写 0~32 的整数：{prefix!r}")
    total = 1 << (32 - prefix)
    return total if total <= 2 else total - 2      # /31 与 /32 是例外，不减 2


def usable_range(cidr):
    """可分配地址的首尾（T4）。

    >>> usable_range("192.168.1.100/26")
    ('192.168.1.65', '192.168.1.126')
    >>> usable_range("10.0.0.0/31")
    ('10.0.0.0', '10.0.0.1')
    """
    address, prefix = parse_cidr(cidr)
    first = ip_to_int(address) & mask_of(prefix)
    total = 1 << (32 - prefix)
    if total == 1:                       # /32：就这一台主机
        return int_to_ip(first), int_to_ip(first)
    if total == 2:                       # /31：RFC 3021，两个地址都能用
        return int_to_ip(first), int_to_ip(first + 1)
    return int_to_ip(first + 1), int_to_ip(first + total - 2)


def same_subnet(a, b):
    """两个带前缀长度的地址是否属于同一个网段（T5）。

    >>> same_subnet("192.168.1.65/26", "192.168.1.126/26")
    True
    >>> same_subnet("192.168.1.100/26", "192.168.1.130/26")
    False
    """
    _, prefix_a = parse_cidr(a)
    _, prefix_b = parse_cidr(b)
    if prefix_a != prefix_b:
        raise ValueError(f"两个地址的前缀长度要一致才能比较：/{prefix_a} 与 /{prefix_b}")
    return network_of(a) == network_of(b)


def split(cidr, new_prefix):
    """把一个网段切成等长的子网，返回子网的 CIDR 列表（T5）。

    >>> split("192.168.1.0/24", 26)
    ['192.168.1.0/26', '192.168.1.64/26', '192.168.1.128/26', '192.168.1.192/26']
    """
    address, prefix = parse_cidr(cidr)
    if (isinstance(new_prefix, bool) or not isinstance(new_prefix, int)
            or not prefix <= new_prefix <= 32):
        raise ValueError(f"新的前缀长度要落在 {prefix}~32 之间：{new_prefix!r}")
    start = ip_to_int(address) & mask_of(prefix)
    step = 1 << (32 - new_prefix)         # 每个子网占多少个地址
    count = 1 << (new_prefix - prefix)    # 一共切成多少块
    return [f"{int_to_ip(start + index * step)}/{new_prefix}" for index in range(count)]
