#!/usr/bin/env python3
"""课件配图：检查判定（存在 / 缺文件 / 外链 / 缺 alt）。

配图的来源是科目的图片库 `assets/img/pool/`（索引 `assets/img/pool.md`，见 `image-scout`
与 `lesson-design` 第三节）。**检查这道是必须的**：`gen_home` 的链接自检只扫它自己写出的
主页（根主页 + 科目主页），课件页明确不在它的范围内——没有这道，学生就会看到裂图。

判定按「学生会不会看到坏东西」分：
  · 本地图不存在 → 阻断（裂图）
  · 外链图 → 提示（离线打开会裂）
  · 缺 alt → 提示（裂图时只剩空白，读屏也读不出）
  · 内联 <svg> 不引用文件，不归这道管

用法：python3 scripts/tests/test_lesson_figure.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
       '<rect width="40" height="20" fill="currentColor"/></svg>')

# 图片库里的图片文件：检查只判「文件在不在」，不解码内容，所以占位字节就够。
POOL_FILE = '数组-内存布局-连续存储-cppreference-01.png'
POOL_SRC = f'../assets/img/pool/{POOL_FILE}'
PNG_STUB = b'\x89PNG\r\n\x1a\n' + b'\x00' * 24


def figure(src, alt='左右指针向中间收拢', caption='图 1 · 双指针怎么收拢',
           cls='lesson-figure'):
    alt_attr = f' alt="{alt}"' if alt is not None else ''
    cap = f'\n    <figcaption>{caption}</figcaption>' if caption else ''
    return (f'  <figure class="{cls}">\n    <img src="{src}"{alt_attr}>{cap}\n  </figure>\n')


# (说明, 图片库里的文件（None = 不写文件）, 课件里的 figure HTML, 该不该拦, 提示里要含)
CASES = [
    ('本地图存在（放行）', POOL_FILE, figure(POOL_SRC), False, None),
    ('本地图不存在（拦）', None,
     figure('../assets/img/pool/哈希表-冲突处理-链地址法-oi-wiki-02.png'), True, '不存在的文件'),
    ('外链图（放行 + 提示）', None, figure('https://example.com/x.png'), False, '外链'),
    ('缺 alt（放行 + 提示）', POOL_FILE, figure(POOL_SRC, alt=None), False, 'alt'),
    ('内联 SVG（放行，不需要文件）', None,
     '  <figure class="lesson-figure lesson-figure--inline">\n    ' + SVG + '\n  </figure>\n',
     False, None),
]


def main():
    tmp = tempfile.mkdtemp(prefix='smtest-figure-')
    subject = fixtures.write_subject(tmp, nodes=[('solo-node', '概念', '唯一节点')])
    img_dir = os.path.join(subject, 'assets', 'img', 'pool')
    os.makedirs(img_dir, exist_ok=True)
    failures = 0
    for label, image, html, want_fail, must in CASES:
        fixtures.clear_lessons(subject)
        for name in os.listdir(img_dir):
            os.remove(os.path.join(img_dir, name))
        if image:
            with open(os.path.join(img_dir, image), 'wb') as handle:
                handle.write(PNG_STUB)
        path = fixtures.write_lesson(subject, 1, 'solo-node', nav=[], extra=html)
        code, out = fixtures.run_gate(path, subject, 'solo-node')
        ok = (code != 0) == want_fail and (not must or must in out)
        failures += not ok
        fixtures.check(label, ok, out if not ok else f'检查={"FAIL" if code else "OK"}')
    total = len(CASES)
    print(f'\n{total - failures}/{total} 通过')
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
