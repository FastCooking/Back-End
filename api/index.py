import os
import sys
from pathlib import Path

# Garante que o diretório raiz esteja no sys.path para resolução de imports 'src.*'
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.app import app
