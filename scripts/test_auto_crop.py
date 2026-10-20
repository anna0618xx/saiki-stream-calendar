"""Offline invariants; CI never downloads videos."""
import tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from crop_screenshots import box_for_face,propose_boxes,crop_one
from collect_public_frames import eligible,choose

class AutoCropTests(unittest.TestCase):
 def test_face_crop_upper_body(self):
  left,top,right,bottom=box_for_face((1280,720),(910,180,105,110))
  self.assertTrue(0<=left<right<=1280 and 0<=top<bottom<=720)
  self.assertAlmostEqual((right-left)/(bottom-top),.8,delta=.02)
  self.assertLess(top,180)
  self.assertGreater(bottom,290)
 def test_no_face_offers_three_options(self):
  with patch('crop_screenshots.find_faces',return_value=[]):
   opts=propose_boxes(Image.new('RGB',(1280,720)))
  self.assertEqual([x[0] for x in opts],['left','center','right'])
  self.assertEqual(len({box for label,box in opts}),3)
 def test_collab_fallback(self):
  with patch('crop_screenshots.find_faces',return_value=[(100,50,90,90),(650,70,87,87)]):
   self.assertEqual(len(propose_boxes(Image.new('RGB',(1280,720)))),3)
 def test_save_candidate(self):
  with tempfile.TemporaryDirectory() as directory,patch('crop_screenshots.find_faces',return_value=[(800,90,110,110)]):
   crop=crop_one(Image.new('RGB',(1280,720),'#a7a4a0'),Path(directory),'test')
   self.assertEqual(len(crop),1)
   self.assertTrue(Path(crop[0]['file']).is_file())
   self.assertTrue(crop[0]['requiresReview'])
 def test_only_public_self_ended(self):
  rec={'videoId':'aBcDE123_-x','channelType':'self','candidate':False,'status':'ended','available':True,
       'start':'2026-10-10T18:00:00Z','end':'2026-10-10T20:00:00Z'}
  self.assertTrue(eligible(rec))
  self.assertFalse(eligible({**rec,'candidate':True}))
  self.assertFalse(eligible({**rec,'channelType':'other'}))
  self.assertFalse(eligible({**rec,'status':'live'}))
  now=datetime(2026,10,20,tzinfo=timezone.utc)
  self.assertEqual(len(choose([rec],set(),{},now)),1)
  self.assertEqual(choose([rec],set(),{rec['videoId']:{'at':now.isoformat()}},now),[])

if __name__=='__main__':unittest.main()
