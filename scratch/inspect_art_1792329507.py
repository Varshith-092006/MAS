import sqlite3, json
conn = sqlite3.connect('mas.db')
c = conn.cursor()
for r in c.execute("SELECT * FROM artifacts WHERE run_id='mas_dev_toc_a_p2m_1792329507'").fetchall():
    print(r[0], r[1], r[2], r[3], r[4])
    try:
        d = json.loads(r[5])
        print('  Keys:', list(d.keys()))
        if 'file_contents' in d:
            print('  file_contents keys:', list(d['file_contents'].keys()))
            for k, v in d['file_contents'].items():
                print(f'    {k}: {repr(v[:100])}')
    except Exception as e:
        print('  Error parsing json:', e)
