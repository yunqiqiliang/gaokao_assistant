#!/usr/bin/env python3
"""
高校招生章程深度爬取脚本（Phase 1.5b）
========================================

用途：
    针对各高校招生网的子页面深度爬取招生章程，
    提取更详细的身体限制、单科要求等信息。

数据来源：
    各高校本科招生网的招生章程子页面

运行方式：
    python3 dim_admission_regulation_deep_scraper.py
"""
import urllib.request, json, time, os, re
import clickzetta

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# 招生章程子页面 URL 模式（需要手动维护）
REGULATION_URLS = {
    # 清华大学
    140: [
        "https://www.join-tsinghua.edu.cn/bkzhaosheng/policy/regulation.htm",
        "https://www.join-tsinghua.edu.cn/bkzhaosheng/policy/regulation2026.htm",
    ],
    # 北京大学
    31: [
        "https://bkzs.pku.edu.cn/zszc/index.htm",
        "https://bkzs.pku.edu.cn/zszc/2026zs.htm",
    ],
    # 上海交通大学
    125: [
        "https://admissions.sjtu.edu.cn/info/1011/1001.htm",
    ],
    # 复旦大学
    132: [
        "https://ao.fudan.edu.cn/zszc/1.htm",
    ],
    # 浙江大学
    114: [
        "https://zdzsc.zju.edu.cn/zszc/list.htm",
    ],
    # 武汉大学
    42: [
        "https://aoff.whu.edu.cn/zszc.htm",
    ],
    # 华中科技大学
    127: [
        "https://zsb.hust.edu.cn/zszc.htm",
    ],
    # 中山大学
    104: [
        "https://admission.sysu.edu.cn/zszc",
    ],
    # 西安交通大学
    330: [
        "https://zs.xjtu.edu.cn/zszc.htm",
    ],
    # 哈尔滨工业大学
    34: [
        "https://zsb.hit.edu.cn/zszc.htm",
    ],
    # 同济大学
    73: [
        "https://bkzs.tongji.edu.cn/zszc.htm",
    ],
    # 天津大学
    60: [
        "https://zs.tju.edu.cn/zszc.htm",
    ],
    # 南开大学
    59: [
        "https://www.nankai.edu.cn/239/list.htm",
    ],
    # 厦门大学
    102: [
        "https://zs.xmu.edu.cn/zszc.htm",
    ],
    # 四川大学
    99: [
        "https://zs.scu.edu.cn/zszc.htm",
    ],
    # 山东大学
    126: [
        "https://www.bkzs.sdu.edu.cn/zszc.htm",
    ],
    # 吉林大学
    122: [
        "https://zsb.jlu.edu.cn/zszc.htm",
    ],
    # 中南大学
    123: [
        "https://zhaosheng.csu.edu.cn/zszc.htm",
    ],
    # 湖南大学
    44: [
        "https://admi.hnu.edu.cn/zszc.htm",
    ],
    # 重庆大学
    119: [
        "https://zhaosheng.cqu.edu.cn/zszc.htm",
    ],
    # 电子科技大学
    661: [
        "https://zs.uestc.edu.cn/zszc.htm",
    ],
    # 西北工业大学
    107: [
        "https://zsb.nwpu.edu.cn/zszc.htm",
    ],
    # 大连理工大学
    138: [
        "https://zs.dlut.edu.cn/zszc.htm",
    ],
    # 华南理工大学
    105: [
        "https://admission.scut.edu.cn/zszc.htm",
    ],
    # 东南大学
    109: [
        "https://zsb.seu.edu.cn/zszc.htm",
    ],
    # 北京航空航天大学
    47: [
        "https://zs.buaa.edu.cn/zszc.htm",
    ],
    # 北京理工大学
    143: [
        "https://admission.bit.edu.cn/zszc.htm",
    ],
    # 北京师范大学
    52: [
        "https://admission.bnu.edu.cn/zszc.htm",
    ],
    # 南京大学
    111: [
        "https://bkzs.nju.edu.cn/zszc.htm",
    ],
    # 中国科学技术大学
    66: [
        "https://zsb.ustc.edu.cn/zszc.htm",
    ],
    # 中国人民大学
    46: [
        "https://rdzs.ruc.edu.cn/cms/zszc/",
    ],
    # 上海财经大学
    130: [
        "https://zs.sufe.edu.cn/zszc.htm",
    ],
    # 中央财经大学
    566: [
        "https://zs.cufe.edu.cn/zszc.htm",
    ],
    # 对外经济贸易大学（需要查 school_id）
    # 中国政法大学（需要查 school_id）
}


def make_conn():
    return clickzetta.connect(
        service=os.environ["CZ_SERVICE"],
        instance=os.environ["CZ_INSTANCE"],
        workspace=os.environ["CZ_WORKSPACE"],
        username=os.environ["CZ_USERNAME"],
        password=os.environ["CZ_PASSWORD"],
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )


def fetch_page(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                return raw.decode(encoding)
            except:
                continue
        return raw.decode('utf-8', errors='replace')
    except Exception as e:
        return None


def sanitize_for_sql(s):
    if s is None:
        return None
    s = str(s)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
    s = s.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    s = s.replace('\\', '')
    return s


def esc_sql(v):
    if v is None:
        return 'NULL'
    if isinstance(v, int):
        return str(v)
    s = sanitize_for_sql(v)
    s = s.replace("'", "''")
    return f"'{s}'"


def extract_regulation_info(html_text):
    if not html_text:
        return None
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = re.sub(r'\s+', ' ', text).strip()
    info = {
        'body_restriction': '',
        'single_subject_req': '',
        'language_restriction': '',
        'gender_ratio': '',
        'other_restrictions': '',
    }
    body_keywords = [
        r'视力.{0,20}(?:(?:不低|低于|要求|须|应).{0,10}(?:4\.[0-9]|5\.[0-9]))',
        r'色盲|色弱|色觉.{0,10}(?:异常|不合格|受限)',
        r'身高.{0,20}(?:(?:不低|低于|要求|须|应).{0,10}(?:1[5-7][0-9]))',
        r'(?:裸眼|矫正).{0,10}视力',
    ]
    for kw in body_keywords:
        matches = re.findall(kw, text)
        if matches:
            info['body_restriction'] += '; '.join(matches) + '; '
    single_keywords = [
        r'(?:英语|外语|语文|数学).{0,15}(?:不低|低于|要求|须|应).{0,10}(?:\d{2,3})',
    ]
    for kw in single_keywords:
        matches = re.findall(kw, text)
        if matches:
            info['single_subject_req'] += '; '.join(matches) + '; '
    lang_keywords = [
        r'外语语种.{0,20}(?:仅限|只招|限于|要求).{0,10}英语',
        r'非英语.{0,10}(?:考生|语种).{0,10}(?:慎报|受限)',
    ]
    for kw in lang_keywords:
        matches = re.findall(kw, text)
        if matches:
            info['language_restriction'] += '; '.join(matches) + '; '
    gender_keywords = [
        r'男女.{0,20}(?:比例|比).{0,10}(?:\d+:\d+)',
    ]
    for kw in gender_keywords:
        matches = re.findall(kw, text)
        if matches:
            info['gender_ratio'] += '; '.join(matches) + '; '
    has_content = any(v.strip() for v in info.values())
    if not has_content:
        info['other_restrictions'] = text[:2000]
    return info


def main():
    t_start = time.time()
    total_urls = sum(len(urls) for urls in REGULATION_URLS.values())
    print(f"待爬取: {len(REGULATION_URLS)} 所高校，共 {total_urls} 个 URL")
    
    conn = make_conn()
    cur = conn.cursor()
    
    rows = []
    success = 0
    failed = 0
    
    for school_id, urls in REGULATION_URLS.items():
        print(f"\n[{success+failed+1}/{len(REGULATION_URLS)}] school_id={school_id}")
        for url_idx, url in enumerate(urls):
            print(f"  URL {url_idx+1}: {url[:60]}...")
            html = fetch_page(url)
            if not html:
                print(f"    失败")
                failed += 1
                continue
            
            info = extract_regulation_info(html)
            if info:
                now = time.strftime('%Y-%m-%d %H:%M:%S')
                row = (
                    school_id, 2026,
                    info['body_restriction'][:500] or None,
                    info['single_subject_req'][:500] or None,
                    info['language_restriction'][:500] or None,
                    info['gender_ratio'][:500] or None,
                    info['other_restrictions'][:500] or None,
                    url, sanitize_for_sql(html[:2000]), now,
                )
                rows.append(row)
                success += 1
                flags = []
                if info['body_restriction']: flags.append('body')
                if info['single_subject_req']: flags.append('single')
                if info['language_restriction']: flags.append('lang')
                print(f"    OK {' '.join(flags) if flags else '(无匹配)'}")
                
                if len(rows) >= 5:
                    insert_rows(cur, rows)
                    conn.commit()
                    rows = []
            time.sleep(2)
    
    if rows:
        insert_rows(cur, rows)
    
    conn.commit()
    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！成功: {success}, 失败: {failed}, 耗时 {elapsed/60:.1f} 分钟")


def insert_rows(cur, rows):
    vals = ', '.join('(' + ', '.join(esc_sql(c) for c in row) + ')' for row in rows)
    cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation VALUES {vals}")


if __name__ == "__main__":
    main()
