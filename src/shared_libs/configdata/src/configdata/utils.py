import csv
from dataclasses import dataclass
from typing import Dict

@dataclass
class ActTableEntry:
    id: int
    id_mask: int
    name: str
    type: str
    size: int

def load_actuator_table(path: str = 'actuator_table.csv') -> Dict[int, ActTableEntry]:
    """
    Loads actuator table from specified .csv file into a dictionary of format:
    
    {   ID *(int)*    ->  Entry *(dataclass with members .id, .name, .type)*   }
    """
    # Open the CSV file
    with open(path, mode='r') as file:
        csv_reader = csv.reader(file)

        try:
            # gets rid of comments and empty lines
            actuator_list = filter(lambda e: (not e[0].startswith("#")) and (e[0].strip() != ""), csv_reader)

            # NOTE actuator_list can only be iterated over ONCE
            actuator_table = {int(id.strip()) : ActTableEntry(int(id.strip()), 1 << (int(id.strip()) - 1), name.strip(), type_.strip(), TYPE_TO_SIZE[type_.strip()]) for id, name, type_ in actuator_list}
        except BaseException as e:
            print("could not load actuator table from csv file; errmsg:")
            print(e)
            return {}
        
        return actuator_table
    

def get_id_by_name_table(actuator_table: Dict[int, ActTableEntry]) -> Dict[str, int]:
    """
    Takes an actuator table dictionary and outputs a dictionary in the format:
    {"actuator name": actuator_ID}.

    actuator_ID is the ID of the actuator (the ID-nth bit of the actuator mask is set to 1)
    """
    return {entry.name : entry.id for entry in actuator_table.values()}
