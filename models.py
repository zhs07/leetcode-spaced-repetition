from dataclasses import dataclass
from datetime import date

@dataclass
class Review:
    problem_number: int
    reviewed_on : date
    mastery_level : str
    
@dataclass
class Problem:
    number : int
    name : str
    difficulty : str
    topic : str
    notes: str
    archived: bool = False
    
    