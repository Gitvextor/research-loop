"""第 3 课 lab · 子网计算器的断言（任务与参考解共用这一份）。

对照答案由标准库 ipaddress 现算，一个数字都不写死：`ipcalc.py` 换成你的实现，
跑的仍然是同一套断言。

    python3 -m unittest -v                             # 全部任务
    python3 -m unittest -v test_ipcalc.TestT1Convert   # 只跑 T1

留白态本来就是红的（函数体是 raise NotImplementedError），跑绿一个任务再往下。
"""
import ipaddress
import unittest

import ipcalc


def oracle(cidr):
    """标准库眼里的这个网段；strict=False 允许写成主机地址。"""
    return ipaddress.ip_network(cidr, strict=False)


class TestT1Convert(unittest.TestCase):
    """T1：点分十进制与 32 位整数互转。"""

    ADDRESSES = ["0.0.0.0", "10.0.0.1", "172.16.30.7", "192.168.1.100", "255.255.255.255"]

    def test_ip_to_int_matches_stdlib(self):
        for text in self.ADDRESSES:
            with self.subTest(text=text):
                self.assertEqual(ipcalc.ip_to_int(text), int(ipaddress.ip_address(text)))

    def test_int_to_ip_matches_stdlib(self):
        for text in self.ADDRESSES:
            with self.subTest(text=text):
                self.assertEqual(ipcalc.int_to_ip(int(ipaddress.ip_address(text))), text)

    def test_round_trip(self):
        self.assertEqual(ipcalc.int_to_ip(ipcalc.ip_to_int("192.168.1.100")), "192.168.1.100")

    def test_rejects_bad_address(self):
        for text in ["192.168.1", "192.168.1.1.1", "192.168.1.256", "192.168.1.x", "192.168.1.-1", ""]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    ipcalc.ip_to_int(text)

    def test_rejects_out_of_range_int(self):
        for value in (-1, 4294967296):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ipcalc.int_to_ip(value)


class TestT2ParseCidr(unittest.TestCase):
    """T2：拆出地址与前缀长度。"""

    def test_splits_address_and_prefix(self):
        self.assertEqual(ipcalc.parse_cidr("192.168.1.100/26"), ("192.168.1.100", 26))

    def test_prefix_boundaries(self):
        self.assertEqual(ipcalc.parse_cidr("0.0.0.0/0"), ("0.0.0.0", 0))
        self.assertEqual(ipcalc.parse_cidr("10.0.0.1/32"), ("10.0.0.1", 32))

    def test_rejects_bad_input(self):
        bad = ["192.168.1.1", "/26", "192.168.1.1/33", "192.168.1.1/-1",
               "192.168.1.1/abc", "192.168.1.1/26/26", "192.168.1.256/24"]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    ipcalc.parse_cidr(text)


class TestT3Network(unittest.TestCase):
    """T3：网络地址、广播地址与可用个数。"""

    CIDRS = ["192.168.1.100/26", "192.168.1.0/24", "10.0.0.0/8", "172.16.30.7/12",
             "10.1.2.3/30", "0.0.0.0/0", "255.255.255.255/32"]

    def test_network_address_matches_stdlib(self):
        for cidr in self.CIDRS:
            with self.subTest(cidr=cidr):
                self.assertEqual(ipcalc.network_of(cidr), str(oracle(cidr).network_address))

    def test_broadcast_address_matches_stdlib(self):
        for cidr in self.CIDRS:
            with self.subTest(cidr=cidr):
                self.assertEqual(ipcalc.broadcast_of(cidr), str(oracle(cidr).broadcast_address))

    def test_host_count_small_prefixes(self):
        for prefix in range(24, 33):
            with self.subTest(prefix=prefix):
                net = oracle(f"10.0.0.0/{prefix}")
                self.assertEqual(ipcalc.host_count(prefix), len(list(net.hosts())))

    def test_host_count_large_prefixes(self):
        for prefix in (0, 8, 12, 16, 20, 24, 30, 31, 32):
            with self.subTest(prefix=prefix):
                net = oracle(f"10.0.0.0/{prefix}")
                expected = net.num_addresses if net.num_addresses <= 2 else net.num_addresses - 2
                self.assertEqual(ipcalc.host_count(prefix), expected)

    def test_rejects_bad_prefix(self):
        for prefix in (-1, 33):
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError):
                    ipcalc.host_count(prefix)


class TestT4Usable(unittest.TestCase):
    """T4：可用地址范围，含 /31 与 /32 两个例外。"""

    CIDRS = ["192.168.1.100/26", "192.168.1.0/24", "172.16.30.7/29",
             "10.0.0.0/30", "10.0.0.0/31", "10.0.0.1/32"]

    def test_usable_range_matches_stdlib(self):
        for cidr in self.CIDRS:
            with self.subTest(cidr=cidr):
                hosts = list(oracle(cidr).hosts())
                self.assertEqual(ipcalc.usable_range(cidr), (str(hosts[0]), str(hosts[-1])))

    def test_range_width_matches_host_count(self):
        for cidr in self.CIDRS:
            with self.subTest(cidr=cidr):
                prefix = int(cidr.rsplit("/", 1)[1])
                first, last = ipcalc.usable_range(cidr)
                width = ipcalc.ip_to_int(last) - ipcalc.ip_to_int(first) + 1
                self.assertEqual(width, ipcalc.host_count(prefix))

    def test_point_to_point_keeps_both_addresses(self):
        self.assertEqual(ipcalc.usable_range("10.0.0.0/31"), ("10.0.0.0", "10.0.0.1"))

    def test_single_host_is_its_own_range(self):
        self.assertEqual(ipcalc.usable_range("10.0.0.7/32"), ("10.0.0.7", "10.0.0.7"))


class TestT5SameAndSplit(unittest.TestCase):
    """T5：判断同网段与切分子网。"""

    def test_same_subnet_true(self):
        self.assertTrue(ipcalc.same_subnet("192.168.1.65/26", "192.168.1.126/26"))
        self.assertTrue(ipcalc.same_subnet("10.0.7.129/26", "10.0.7.190/26"))

    def test_same_subnet_false(self):
        self.assertFalse(ipcalc.same_subnet("192.168.1.100/26", "192.168.1.130/26"))
        self.assertFalse(ipcalc.same_subnet("10.0.7.190/26", "10.0.7.200/26"))

    def test_same_subnet_rejects_mixed_prefixes(self):
        with self.assertRaises(ValueError):
            ipcalc.same_subnet("192.168.1.1/24", "192.168.1.1/25")

    def test_split_matches_stdlib(self):
        cases = [("192.168.1.0/24", 26), ("192.168.1.0/24", 27),
                 ("10.0.0.0/8", 10), ("192.168.1.0/26", 26)]
        for cidr, new_prefix in cases:
            with self.subTest(cidr=cidr, new_prefix=new_prefix):
                expected = [str(net) for net in oracle(cidr).subnets(new_prefix=new_prefix)]
                self.assertEqual(ipcalc.split(cidr, new_prefix), expected)

    def test_split_rejects_impossible_prefix(self):
        for new_prefix in (20, 33):
            with self.subTest(new_prefix=new_prefix):
                with self.assertRaises(ValueError):
                    ipcalc.split("192.168.1.0/24", new_prefix)


if __name__ == "__main__":
    unittest.main()
