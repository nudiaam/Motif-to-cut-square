"""Manual photographic QA landmarks, never passed to the detector.

Corners and seams were read on the original photos. They are approximate visual
measurements (six source pixels), not a machine calibration. Witnesses sample
real details, and cannot certify every pixel of the composition.
"""
CASES={
 'beige':{'shape':(6,4),'quad':((92,60),(1494,145),(1488,1000),(10,948)),
          'witnesses':[[(197,126),(193,255)],[(370,135),(490,270)],[(130,760),(180,930)]]},
 'shadow':{'shape':(6,4),'quad':((56,48),(1480,52),(1480,980),(44,982)),
           'witnesses':[[(350,590),(488,714)],[(632,345),(654,478)],[(934,70),(934,246)]]},
 'faint':{'shape':(6,4),'quad':((80,62),(1450,60),(1478,964),(68,962)),
          'reference_note':'Bottom-right printed frame remeasured on original with pixel rulers: (1478,964), previously (1464,960). Uneven inner spacing remains approximate.',
          'witnesses':[[(436,108),(420,270)],[(432,765),(420,927)],[(625,555),(700,705)]]},
 'accessories':{'shape':(4,3),'quad':((50,86),(1484,94),(1486,946),(40,946)),
   'witnesses':[[(160,260),(330,205),(330,330)],[(550,250),(690,190),(690,320)],[(910,810),(1060,765),(1050,890)]]},
 'holdout_accessories_4x3':{'shape':(4,3),'quad':((112,117),(1418,113),(1502,941),(37,947))},
 'holdout_pale_5x4':{'shape':(5,4),'quad':((166,48),(1425,103),(1416,957),(81,922))},
 'holdout_birds_7x3':{'shape':(7,3),'quad':((60,214),(1472,216),(1534,854),(0,858))},
 'partial':{'shape':(6,3),'xs':(28,298,550,790,1026,1260,1536),'ys':(76,378,624,894),
            'witnesses':[[(188,125),(188,337)],[(925,105),(909,348)]]},
 'square_animals_6x4':{'shape':(6,4),'xs':(75,307,539,771,1004,1234,1460),'ys':(48,286,512,739,974),
   'witnesses':[[(198,100),(215,249),(132,237),(265,242)],[(409,110),(435,237),(505,239)]]},
 'square_offcentre_5x3':{'shape':(5,3),'xs':(65,348,625,905,1187,1474),'ys':(104,378,645,928),
   'witnesses':[[(160,185),(175,330),(277,216),(280,302)],[(440,192),(430,331),(555,210),(555,309)],
                [(715,190),(720,330),(830,215),(830,300)]]}
}
