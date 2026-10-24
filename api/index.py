import os
import sys

# Permet d'importer main.py et le catalogue depuis la racine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app