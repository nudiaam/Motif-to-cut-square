"""Fail setup visibly if imports or required bundled assets are incomplete."""
from pathlib import Path
import sys


def verify_installation():
    import cv2
    import numpy as np
    import PySide6
    import app.main  # Loads the same application imports as the launcher.

    root=Path(__file__).resolve().parents[2]
    for relative in ('app/assets/lalikul-cut-prep.ico', 'app/assets/lalikul-cut-prep.png',
                     'assets/references/epilog/empty_bed.png'):
        path=root/relative
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError('Missing application file: '+relative+'. Extract the entire ZIP again.')
    # Decode the bundled reference directly, independently of personal settings.
    reference=cv2.imdecode(np.frombuffer((root/'assets/references/epilog/empty_bed.png').read_bytes(),np.uint8),cv2.IMREAD_COLOR)
    if reference is None:
        raise RuntimeError('The bundled empty-bed image cannot be read. Extract the entire ZIP again.')
    cv2.cvtColor(np.zeros((4,4,3),np.uint8),cv2.COLOR_BGR2LAB)
    return {'python':sys.version.split()[0], 'PySide6':PySide6.__version__,
            'opencv':cv2.__version__, 'numpy':np.__version__}


if __name__=='__main__':
    try:
        versions=verify_installation()
    except Exception as error:
        print('Application verification failed: '+str(error),file=sys.stderr)
        raise SystemExit(1)
    print('Application imports and bundled files verified: '+str(versions))
