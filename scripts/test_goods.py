import unittest
from collect_goods import candidate, dates_in_line, extract_goods_from_schedule, extract_goods_from_announcements

class GoodsCollectorTest(unittest.TestCase):
    def test_explicit_dates_and_times(self):
        line="追加グッズ受注販売期間：2026年10月10日(土)21時～10月25日(日)23時59分"
        self.assertEqual(dates_in_line(line,2026),["2026-10-10T21:00","2026-10-25T23:59"])

    def test_only_specific_schedule_remarks(self):
        sample='''<table><tr><td>10月25日（日）</td><td></td><td></td><td></td><td></td><td>“Over Drive!”追加グッズ受注販売終了</td></tr></table>'''
        rows=extract_goods_from_schedule(sample.encode(),"https://wikiwiki.jp/nijisanji/佐伯イッテツ/スケジュール",2026)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["date"],"2026-10-25")
        self.assertEqual(rows[0]["kind"],"deadline")

    def test_promo_dates(self):
        sample='''<h3>グッズ情報</h3><h4>MECHATU-A 1st LIVE "Over Drive!" グッズ</h4>
        <ul><li>追加グッズ受注販売期間：2026年10月10日(土)21時～10月25日(日)23時59分</li></ul>
        <h3>3Dお披露目</h3><ul><li>予約期間：2026年11月1日10時～12月1日23時</li></ul>'''
        rows=extract_goods_from_announcements(sample.encode(),"https://wikiwiki.jp/nijisanji/佐伯イッテツ",2026)
        self.assertEqual([(r["kind"],r["date"]) for r in rows],[("reserveStart","2026-10-10T21:00"),("deadline","2026-10-25T23:59")])

    def test_candidate_stable(self):
        a=candidate("Over Drive! グッズ","2026-10-25T23:59","deadline","https://wikiwiki.jp")
        b=candidate("Over Drive! グッズ","2026-10-25T23:59","deadline","https://wikiwiki.jp")
        self.assertEqual(a["id"],b["id"])

if __name__=="__main__":
    unittest.main()
