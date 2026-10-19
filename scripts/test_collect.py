import io
import unittest
from PIL import Image
from collect import parse_wiki,green_screen_score,id_from_url

class TestCollector(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(id_from_url('https://youtu.be/sfyLkXoiIWg'),'sfyLkXoiIWg')
        self.assertIsNone(id_from_url('https://example.com/watch?v=sfyLkXoiIWg'))

    def test_wiki_source(self):
        src='-01/01 &color(Red){■};[[SF6>https://youtu.be/sfyLkXoiIWg]]\n-01/02 &color(Gray){■};[[Other>https://youtu.be/qYTUhHDLg1I]]\n-01/03 &color(Orange){■};[[Oriens>https://youtu.be/fanHUKyN9xU]]'
        rows=parse_wiki(src.encode())
        self.assertEqual(len(rows),3)
        self.assertEqual(rows['sfyLkXoiIWg']['channelType'],'self')
        self.assertTrue(rows['fanHUKyN9xU']['candidate'])
        self.assertEqual(rows['qYTUhHDLg1I']['channelType'],'other')
        self.assertTrue(rows['qYTUhHDLg1I']['candidate'])

    def test_html(self):
        src='<ul><li>01/01 <span style="color:red">■</span><a href="https://youtu.be/sfyLkXoiIWg">SF6</a></li><li>01/03 <span style="color:gray">■</span><a href="https://youtu.be/qYTUhHDLg1I">Other</a></li></ul>'
        rows=parse_wiki(src.encode())
        self.assertEqual(set(rows),{'sfyLkXoiIWg','qYTUhHDLg1I'})

    def test_actual_wiki_line_shapes(self):
        src="""-01/16 &color(Black){■};[[【直前放送】加賀美ハヤト>https://live.nicovideo.jp/watch/lv349333362]]
-01/18 &color(orange){■};[[マリオパーティ>https://youtu.be/cN-PiqBzs_8]]
-01/31 &color(Gray){■};[[四季凪アキラとの恋愛相談>https://youtu.be/sQ7pGyoBTSs]]
-02/14 &color(gray){■};[[ウエハース>https://youtu.be/SDTUi6m0j-Y]]
-01/25 &color(Gray){■};[[本人の音声なし>https://youtu.be/gNWkL00ccDE]]
"""
        rows=parse_wiki(src.encode())
        self.assertEqual(len(rows),4)
        self.assertEqual(rows['sQ7pGyoBTSs']['channelType'],'other')
        self.assertTrue(rows['sQ7pGyoBTSs']['candidate'])
        self.assertFalse(rows['cN-PiqBzs_8']['channelType']=='self')

    def test_green(self):
        def score(rgb):
            b=io.BytesIO();Image.new('RGB',(300,180),rgb).save(b,format='PNG')
            return green_screen_score(b.getvalue())
        self.assertGreater(score((5,240,10))[0],0.9)
        self.assertLess(score((130,50,85))[0],0.1)

if __name__=='__main__':unittest.main()
