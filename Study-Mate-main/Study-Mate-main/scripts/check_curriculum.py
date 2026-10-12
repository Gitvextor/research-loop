#!/usr/bin/env python3
"""按 schemas/curriculum.schema.json 校验 curriculum.yaml。

用法:
    python3 scripts/check_curriculum.py <curriculum.yaml> [更多.yaml ...]

除了 JSON Schema 校验，还额外检查 schema 管不到的结构性问题：
  - id 重复
  - prerequisites / edges 引用了不存在的节点
  - 实验课 (kind: 实验) 的 prerequisites 是否列了它要验收的普通课
  - 依赖指到了排在它后面的节点（nodes 顺序即教学位次，倒挂会让学生学到还没讲的课）
  - 有向图存在环（prerequisites + edges 合成；DAG 是硬要求）
  - 存在未被任何后续节点依赖的孤儿节点（提示，不算错误）

退出码：全部通过 0；有问题 1；没给参数 2。
（本脚本由课程设计角色在一次实测会话里写出，经总控复核后收编：只读、无副作用。）
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML，请先 pip install pyyaml")
try:
    import jsonschema
except ImportError:
    jsonschema = None

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "curriculum.schema.json"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    failed = False

    for arg in argv[1:]:
        path = Path(arg).resolve()
        print(f"=== {path} ===")
        if not path.is_file():
            print(f"  [ERROR] 文件不存在")
            failed = True
            continue

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            print(f"  [ERROR] 无法读取 YAML：{exc}")
            failed = True
            continue
        if not isinstance(data, dict):
            print("  [ERROR] 顶层不是 mapping")
            failed = True
            continue

        errors: list[str] = []
        if jsonschema is not None:
            validator = jsonschema.Draft7Validator(schema)
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
                loc = "/".join(str(p) for p in err.path) or "<root>"
                errors.append(f"schema  {loc}: {err.message}")
        else:
            print("  [WARN] 未安装 jsonschema，跳过 schema 校验")

        # 结构检查仍会遍历这些字段；schema 报错后不能继续把错误类型当列表/字符串用。
        # 没装 jsonschema 时也保留这道检查，避免 TypeError 中断其余文件。
        structure_errors = []
        for field in ("nodes", "edges"):
            if not isinstance(data.get(field, []), list):
                structure_errors.append(f"{field} 必须是数组")
        if not structure_errors:
            for n in data.get("nodes", []):
                if not isinstance(n, dict) or not isinstance(n.get("id"), str):
                    structure_errors.append("nodes 中每项必须是含字符串 id 的对象")
                    continue
                prerequisites = n.get("prerequisites", [])
                if not isinstance(prerequisites, list) or not all(isinstance(p, str) for p in prerequisites):
                    structure_errors.append(f"{n['id']}: prerequisites 必须是字符串数组")
                if n.get("kind") is not None and not isinstance(n["kind"], str):
                    structure_errors.append(f"{n['id']}: kind 必须是字符串")
            for e in data.get("edges", []):
                if not isinstance(e, dict) or not all(isinstance(e.get(k), str) for k in ("from", "to")):
                    structure_errors.append("edges 中每项必须是含字符串 from/to 的对象")
        if structure_errors:
            failed = True
            print(f"  [FAIL] {len(errors + structure_errors)} 个问题：")
            for msg in errors + structure_errors:
                print(f"    - {msg}")
            continue

        nodes = data.get("nodes") or []
        ids = [n.get("id") for n in nodes if isinstance(n, dict)]
        seen: set[str] = set()
        for nid in ids:
            if nid in seen:
                errors.append(f"重复 id: {nid}")
            seen.add(nid)
        ids = list(dict.fromkeys(ids))

        for n in nodes:
            if not isinstance(n, dict):
                continue
            nid = n.get("id")
            for pre in n.get("prerequisites") or []:
                if pre not in seen:
                    errors.append(f"{nid}: prerequisites 引用了不存在的节点 {pre}")

        for e in data.get("edges") or []:
            if not isinstance(e, dict):
                continue
            for key in ("from", "to"):
                if e.get(key) not in seen:
                    errors.append(f"edge {e.get('from')} -> {e.get('to')}: {key} 指向不存在的节点 {e.get(key)}")

        # 位次倒挂：nodes 的书写顺序就是教学位次（课件文件名 `<序号>-<节点id>.md` 的序号按它算），
        # 所以依赖只能指向前面的节点；指向后面 = 学生还没学就被要求用它。
        pos = {nid: i for i, nid in enumerate(ids)}
        inverted: dict[tuple[str, str], None] = {}
        for n in nodes:
            if not isinstance(n, dict) or n.get("id") not in pos:
                continue
            for pre in n.get("prerequisites") or []:
                if pre in pos and pos[pre] > pos[n["id"]]:
                    inverted.setdefault((n["id"], pre), None)
        for e in data.get("edges") or []:
            if isinstance(e, dict) and e.get("from") in pos and e.get("to") in pos:
                if pos[e["from"]] > pos[e["to"]]:
                    inverted.setdefault((e["to"], e["from"]), None)
        for dep, pre in inverted:
            errors.append(f"{dep}（第 {pos[dep] + 1} 位）依赖 {pre}（第 {pos[pre] + 1} 位）——"
                          f"nodes 顺序即教学位次，依赖只能指向前面的节点")

        # 实验课必须有非空 prerequisites
        for n in nodes:
            if isinstance(n, dict) and n.get("kind") == "实验":
                if not n.get("prerequisites"):
                    errors.append(f"{n.get('id')}: 实验课必须有 prerequisites（列出验收哪些节点）")

        # 环检测（Kahn 拓扑排序）：prerequisites 与 edges 合成一张有向图，DAG 是硬要求。
        # 排序不掉的节点就是环上的节点——比手写 DFS 的颜色标记稳，不存在递归深度问题。
        graph: dict[str, set[str]] = {i: set() for i in ids}
        for n in nodes:
            if isinstance(n, dict) and n.get("id") in graph:
                for pre in n.get("prerequisites") or []:
                    if pre in graph:
                        graph[pre].add(n["id"])
        for e in data.get("edges") or []:
            if isinstance(e, dict) and e.get("from") in graph and e.get("to") in graph:
                graph[e["from"]].add(e["to"])
        indegree = {node: 0 for node in ids}
        for outs in graph.values():
            for nxt in outs:
                indegree[nxt] += 1
        ready = [node for node in ids if indegree[node] == 0]
        settled = 0
        while ready:
            node = ready.pop()
            settled += 1
            for nxt in graph[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        if settled < len(ids):
            stuck = [node for node in ids if indegree[node] > 0]
            errors.append(f"存在环：{len(stuck)} 个节点排不出拓扑序（{', '.join(stuck[:6])}"
                          + ("…" if len(stuck) > 6 else "") + "）")

        # 统计
        kinds: dict[str, int] = {}
        for n in nodes:
            if isinstance(n, dict):
                kinds[n.get("kind")] = kinds.get(n.get("kind"), 0) + 1
        print(f"  节点 {len(nodes)} 个： " + "，".join(f"{k} {v}" for k, v in kinds.items()))
        print(f"  边 {len(data.get('edges') or [])} 条")

        # 孤儿提示
        referenced = {p for n in nodes if isinstance(n, dict) for p in (n.get("prerequisites") or [])}
        referenced |= {e.get("from") for e in (data.get("edges") or []) if isinstance(e, dict)}
        orphans = [i for i in ids if i not in referenced]
        if orphans:
            print(f"  [提示] 没有被任何节点依赖的末端节点: {', '.join(orphans)}")

        if errors:
            failed = True
            print(f"  [FAIL] {len(errors)} 个问题：")
            for msg in errors:
                print(f"    - {msg}")
        else:
            print("  [PASS] schema 校验通过，引用完整")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
