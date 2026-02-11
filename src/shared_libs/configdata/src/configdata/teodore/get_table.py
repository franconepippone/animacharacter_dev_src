import configdata.utils as utls
from pathlib import Path


table_path = Path(__file__).parent / 'table.csv'

def get_table():
    return utls.load_actuator_table(str(table_path.resolve()))

def get_id_by_name_tb():
    return utls.get_id_by_name_table(get_table())