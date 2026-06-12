import sys
sys.path.insert(0, ".")
print("A: inicio")

print("B: import pandas")
import pandas as pd
print("   OK pandas", pd.__version__)

print("C: import loguru")
from loguru import logger
print("   OK loguru")

print("D: reconfigure stdout")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print("   OK reconfigure")

print("E: logger.remove y add a stdout")
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)
print("   OK logger")

print("F: import validators")
from utils.validators import validate_date, validate_amount
print("   OK validators")

print("G: import siigo_parser")
from utils.siigo_parser import parse_siigo_auxiliary
print("   OK siigo_parser")

print("H: import template_agent")
from agents.template_agent import TemplateAgent
print("   OK template_agent")

print("I: TemplateAgent()")
agent = TemplateAgent()
print("   OK agent")

print("FIN")
