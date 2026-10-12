# 计算机网络 Resources

> 定位：**延伸阅读 + 易变内容的核对来源**，不是"知识来源清单"（模型已掌握稳定基础知识）。
> 稳定知识节点可以不在这里留条目；易变/版本相关内容必须在这里有核对过的官方来源。

## Knowledge

- [RFC 9293: Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293.html)
  核对 TCP 首部字段、三次握手与状态机；2022 年取代 RFC 793，第 4 课的术语以它为准。
- [RFC 791: Internet Protocol](https://www.rfc-editor.org/rfc/rfc791.html)
  核对 IPv4 首部字段（版本、TTL、协议号）与分片规则；第 1、3 课讲的「IP 头 20 字节」出自这里。
- [RFC 4632: CIDR 与路由聚合](https://www.rfc-editor.org/rfc/rfc4632.html)
  核对「前缀长度」「网络地址」「广播地址」的正式定义，以及为什么废掉 A/B/C 类划分。
- [RFC 3021: 点对点链路上的 /31 前缀](https://www.rfc-editor.org/rfc/rfc3021.html)
  核对第 3 课 lab 的边界用例：/31 只有两个地址、两个都能用，与 /30 的算法不同。
- [RFC 826: 地址解析协议 ARP](https://www.rfc-editor.org/rfc/rfc826.html)
  核对 IP 地址解析到 MAC 地址的过程；第 2 课讲「同一网段内怎么找到对方」时对照。
- [IEEE 802.3 以太网工作组](https://www.ieee802.org/3/)
  核对以太网帧格式、最小帧长与 CSMA/CD 的现行标准入口；标准正文收费，先用这里的公开概览。
- [MDN: HTTP 概述](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Overview)
  核对一次请求/响应报文的组成与常见首部，用来确定第 1 课里「应用层载荷」的边界。
- [Wireshark 用户指南](https://www.wireshark.org/docs/wsug_html_chunked/)
  第 5 课实验的抓包与显示过滤器用法；「Follow TCP Stream」一节的步骤照它做。
- [tcpdump 手册页](https://www.tcpdump.org/manpages/tcpdump.1.html)
  核对命令行抓包的选项（`-i`、`-n`、`-w`、`-r`）与过滤表达式写法。
- [Python ipaddress 模块](https://docs.python.org/zh-cn/3/library/ipaddress.html)
  第 3 课 lab 的对照实现：手算完用 `ip_network()` 复核，`hosts()` 的边界行为也在这里查。
- [Cisco: IP Addressing and Subnetting for New Users](https://www.cisco.com/c/en/us/support/docs/ip/routing-information-protocol-rip/13788-3.html)
  厂商文档 · 子网划分的算例与掩码速查表，卡住时换一种排版看同一件事。
- [Computer Networking: A Top-Down Approach 作者站（Kurose 与 Ross）](https://gaia.cs.umass.edu/kurose_ross/index.php)
  书 · 配套站上有 Wireshark Labs 与章节讲义；第 5 课实验的题目可以照它的 Wireshark Lab 改，讲义用来换一种讲法看同一件事。

## Wisdom (Communities)

- [Server Fault](https://serverfault.com/)
  排障类提问（"这个端口为什么连不上"）；附上抓包片段与 `ip addr` 输出更容易得到答复。
- [Network Engineering Stack Exchange](https://networkengineering.stackexchange.com/)
  协议行为与设备配置的问答；查「同一个现象在标准里怎么规定」时比论坛靠谱。
- [Wireshark Q&A](https://ask.wireshark.org/)
  抓包文件看不懂时贴上去问；问之前先自己用显示过滤器缩到一条流。

## Gaps

- 缺中文的、以抓包为主线按「一次请求的时间线」组织的入门材料；目前靠 Wireshark 用户指南与教材第 1 章互补。
- 无线侧（802.11 的帧格式与管理帧）没找到合适的免费一手资料，本轮不深入，第 2 课只讲「无线帧会被翻译成以太网帧」这一层结论。
