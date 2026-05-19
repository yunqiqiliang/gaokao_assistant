#!/usr/bin/env python3
"""
高校招生章程采集脚本（Phase 1.5）
===================================

用途：
    爬取各高校本科招生网的2026年招生章程，提取关键约束信息入库。

数据来源：
    各高校本科招生网（从 gaokao.cn info.json 的 site 字段自动获取）

运行方式：
    python3 dim_admission_regulation_scraper.py
"""
import urllib.request, json, time, os, re
import clickzetta

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

ADMISSION_URLS = {
    31: "https://bkzs.pku.edu.cn/",
    33: "https://bkzs.dlmu.edu.cn",
    34: "https://zsb.hit.edu.cn/",
    36: "https://zsb.chd.edu.cn",
    37: "https://zsb.nwu.edu.cn/",
    38: "https://zsw.bjtu.edu.cn",
    42: "https://aoff.whu.edu.cn/",
    44: "https://admi.hnu.edu.cn",
    46: "https://rdzs.ruc.edu.cn/cms/",
    47: "https://zs.buaa.edu.cn/index.htm",
    48: "https://zsb.bupt.edu.cn/",
    51: "https://zhaosheng.swjtu.edu.cn/",
    52: "https://admission.bnu.edu.cn/",
    57: "https://zsb.xidian.edu.cn",
    59: "https://www.nankai.edu.cn/239/list.htm",
    60: "https://zs.tju.edu.cn/",
    61: "https://bkzs.ouc.edu.cn",
    62: "http://ao.zzu.edu.cn",
    63: "https://bkzs.hfut.edu.cn/",
    71: "https://admission.ujn.edu.cn/",
    73: "https://bkzs.tongji.edu.cn/",
    76: "https://bkzsw.shu.edu.cn/",
    77: "https://zs.nuaa.edu.cn",
    81: "https://zsb.tjut.edu.cn/",
    82: "https://zsb.tust.edu.cn/",
    84: "https://zhaosheng.tjufe.edu.cn/",
    85: "https://zs.tjcu.edu.cn",
    86: "https://admission.jiangnan.edu.cn/",
    88: "https://www.cauc.edu.cn/zsb/",
    97: "https://zsb.lzu.edu.cn",
    99: "https://zs.scu.edu.cn",
    101: "https://zb.swufe.edu.cn/",
    102: "https://zs.xmu.edu.cn/",
    104: "https://admission.sysu.edu.cn",
    105: "https://admission.scut.edu.cn/",
    106: "https://zsb.jnu.edu.cn",
    107: "https://zsb.nwpu.edu.cn",
    108: "https://zjc.ncu.edu.cn/zs/",
    109: "https://zsb.seu.edu.cn/",
    111: "https://bkzs.nju.edu.cn",
    112: "https://zsb.njust.edu.cn/",
    114: "https://zdzsc.zju.edu.cn",
    116: "https://zsw.hhu.edu.cn/",
    118: "https://zsb.suda.edu.cn",
    119: "https://zhaosheng.cqu.edu.cn",
    122: "https://zsb.jlu.edu.cn",
    123: "https://zhaosheng.csu.edu.cn/",
    125: "https://admissions.sjtu.edu.cn",
    126: "https://www.bkzs.sdu.edu.cn/",
    127: "https://zsb.hust.edu.cn/",
    128: "https://zs.whut.edu.cn",
    130: "https://zs.sufe.edu.cn/",
    131: "https://zsb.ecnu.edu.cn/",
    132: "https://ao.fudan.edu.cn/",
    133: "https://zsb.ecust.edu.cn/",
    134: "http://zs.neu.edu.cn/",
    138: "https://zs.dlut.edu.cn/",
    139: "https://zs.tyut.edu.cn/",
    140: "https://www.join-tsinghua.edu.cn",
    143: "https://admission.bit.edu.cn",
    144: "https://zhaosheng.ustb.edu.cn",
    164: "https://bkzs.nufe.edu.cn/",
    187: "https://zs.cqut.edu.cn/",
    220: "https://recruit.djtu.edu.cn/",
    229: "https://zs.dufe.edu.cn/",
    232: "https://www.zs.cdut.edu.cn",
    284: "https://zs.szu.edu.cn",
    293: "https://zsjy.gzhu.edu.cn/",
    307: "https://zhaoban.usst.edu.cn/",
    310: "https://ygzs.shutcm.edu.cn/",
    330: "https://zs.xjtu.edu.cn/",
    332: "https://zhshw.nwsuaf.edu.cn",
    342: "https://www.kmust.edu.cn/zsjy/bkszs.htm",
    349: "https://zhaosheng.xaut.edu.cn/",
    385: "https://zs.xtu.edu.cn/",
    391: "https://zsw.usc.edu.cn/",
    414: "https://bkzs.zuel.edu.cn/",
    428: "https://zszc.yangtzeu.edu.cn",
    459: "https://zs.henu.edu.cn/",
    460: "https://zjc.haust.edu.cn/zsxxwsy.htm",
    463: "https://www6.hpu.edu.cn/web5/zsxxw.htm",
    464: "https://www2.ncwu.edu.cn/zhaoshengwang/",
    471: "https://zsb.jmu.edu.cn/",
    499: "https://zs.qdu.edu.cn/",
    504: "https://bkzs.hainanu.edu.cn/",
    507: "https://zs.qust.edu.cn/",
    509: "https://zhaosheng.qut.edu.cn/",
    528: "https://zsb.sdjzu.edu.cn/",
    537: "https://zs.sdust.edu.cn/",
    540: "https://zszx.sdut.edu.cn/",
    554: "https://bkzs.ytu.edu.cn/",
    558: "https://zhaosheng.cuc.edu.cn",
    566: "https://zs.cufe.edu.cn/",
    661: "https://zs.uestc.edu.cn/",
    934: "http://bkzsw.swu.edu.cn/",
    1018: "https://zs.cqjtu.edu.cn/",
    1073: "https://acgozs.ctbu.edu.cn/",
    1249: "https://zs.hntou.edu.cn/",
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
    """清理字符串，移除可能破坏 SQL 的字符"""
    if s is None:
        return None
    s = str(s)
    # 移除控制字符（除了空格）
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
    # 移除换行、回车、制表符
    s = s.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # 移除反斜杠（ClickZetta 可能将其视为转义）
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


def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_admission_regulation")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_admission_regulation (
            school_id INT,
            regulation_year INT,
            body_restriction STRING,
            single_subject_req STRING,
            language_restriction STRING,
            gender_ratio STRING,
            other_restrictions STRING,
            source_url STRING,
            raw_text STRING,
            crawl_time STRING
        ) COMMENT '高校招生章程关键约束信息'
    """)
    conn.commit()


def main():
    t_start = time.time()
    print(f"待采集: {len(ADMISSION_URLS)} 所高校的招生章程")
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    rows = []
    success = 0
    failed = 0
    for school_id, url in ADMISSION_URLS.items():
        print(f"  [{success+failed+1}/{len(ADMISSION_URLS)}] sid={school_id}: {url[:60]}...")
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
