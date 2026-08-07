import sys

bundle_root = getattr(sys, "_MEIPASS", None)
if bundle_root and bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)
