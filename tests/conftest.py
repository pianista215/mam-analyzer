import sys, os
# Inserta `src/` en sys.path para que Python vea el paquete mam_analyzer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
# Inserta `tests/` en sys.path para módulos compartidos como runway_data
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))