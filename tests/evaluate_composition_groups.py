"""Independent complete-group witnesses for mixed luminance and colour scenes."""
from pathlib import Path
from dataclasses import asdict
import json,argparse,time
import cv2,numpy as np
from app.imaging.detector import MotifDetector
from tests.evaluate_accessory_columns import variants

POINTS={'cocktails': [[(181, 263), (248, 186), (259, 303), (269, 350), (182, 356)], [(411, 263), (459, 194), (482, 249), (503, 333), (415, 358)], [(625, 283), (674, 193), (709, 277), (724, 351), (625, 354)], [(865, 264), (903, 194), (943, 249), (952, 340), (865, 350)], [(1087, 289), (1127, 189), (1161, 236), (1180, 352), (1091, 357)], [(1306, 280), (1367, 189), (1388, 252), (1394, 343), (1308, 356)], [(182, 542), (207, 436), (259, 557), (288, 544), (268, 601)], [(408, 541), (453, 445), (496, 507), (503, 591), (410, 597)], [(633, 509), (680, 449), (714, 519), (729, 601), (633, 604)], [(864, 536), (897, 436), (940, 504), (953, 587), (865, 612)], [(1096, 524), (1154, 494), (1174, 545), (1187, 603), (1093, 610)], [(1322, 550), (1389, 460), (1408, 551), (1401, 586), (1322, 604)], [(190, 795), (244, 689), (272, 755), (283, 858), (194, 863)], [(412, 807), (450, 729), (512, 789), (514, 850), (417, 855)], [(643, 738), (689, 674), (719, 778), (725, 853), (643, 853)], [(856, 806), (919, 697), (943, 771), (953, 850), (859, 857)], [(1096, 811), (1168, 722), (1189, 820), (1177, 853), (1098, 855)], [(1320, 805), (1394, 685), (1392, 822), (1394, 857), (1320, 852)]], 'quotes': [[(407, 164), (457, 210), (373, 264), (475, 265)], [(664, 164), (657, 213), (598, 263), (713, 263)], [(867, 165), (891, 213), (832, 260), (946, 261)], [(1118, 164), (1194, 213), (1050, 260), (1198, 264)], [(407, 367), (357, 405), (491, 405), (347, 475), (489, 475)], [(635, 366), (699, 401), (601, 457), (708, 467)], [(889, 366), (849, 400), (832, 462), (951, 462)], [(1128, 366), (1055, 407), (1215, 406), (1071, 469), (1192, 469)], [(407, 560), (458, 608), (342, 679), (495, 679)], [(615, 560), (692, 605), (585, 674), (727, 673)], [(889, 559), (890, 606), (825, 667), (953, 674)], [(1127, 560), (1177, 606), (1090, 672), (1154, 671)], [(384, 759), (422, 809), (345, 872), (494, 871)], [(638, 759), (698, 811), (591, 865), (706, 866)], [(878, 759), (898, 809), (833, 865), (974, 870)], [(1082, 759), (1201, 810), (1080, 864), (1218, 873)]]}

def assess(result,transform,name):
    owners=[];misses=[]
    for idx,points in enumerate(POINTS[name]):
        mapped=cv2.perspectiveTransform(np.asarray(points,float).reshape(-1,1,2),transform).reshape(-1,2)
        hits=[i for i,c in enumerate(result.candidates) if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in mapped)]
        if len(hits)!=1:misses.append(idx+1)
        else:owners.extend(hits)
    return {'whole_groups':len(set(owners)),'failed_groups':misses}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();records=[]
    for name in POINTS:
        image=cv2.imread(f'tests/fixtures/customer_20261012/{name}_groups.png')
        for variation,pixels,transform,settings in variants(image):
            d=MotifDetector();started=time.perf_counter();r=d.detect_with_layout(pixels,settings)
            record={'source':name,'variant':variation,'count':len(r.candidates),'seconds':time.perf_counter()-started,**assess(r,transform,name),'result':asdict(r),'diagnostics':d.last_diagnostics}
            records.append(record);Path(args.output).write_text(json.dumps(records,indent=2));print(name,variation,record['count'],record['whole_groups'],record['failed_groups'],flush=True)
