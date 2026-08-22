"""Comprehensive Question Bank with 150 categorized questions.

Sections:
1. LOGICAL REASONING (50 Questions)
   - Number Series, Letter Series, Coding-Decoding, Blood Relations, Direction Sense,
     Syllogisms, Analogies, Odd One Out, Seating Arrangement, Logical Puzzles, Statement & Conclusion.

2. QUANTITATIVE APTITUDE (50 Questions)
   - Percentages, Profit and Loss, Ratio and Proportion, Average, Time and Work,
     Time Speed Distance, Simple Interest, Compound Interest, Probability,
     Permutation and Combination, Number System, Ages.

3. TECHNICAL APTITUDE (50 Questions)
   - Java, Python, C/C++, OOP, DBMS, SQL, Operating Systems, Computer Networks,
     Data Structures, Algorithms, HTML, CSS, JavaScript.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# =========================================================================
# 1. LOGICAL REASONING (50 Questions)
# =========================================================================
LOGICAL_QUESTIONS: List[Dict[str, Any]] = [
    # Number Series (1-5)
    {"section": "LOGICAL", "question_text": "Look at the sequence: 3, 8, 18, 38, 78, ?. What number should replace the question mark?", "option_a": "148", "option_b": "156", "option_c": "158", "option_d": "162", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "What is the next number in the prime squares sequence: 4, 9, 25, 49, 121, ?", "option_a": "144", "option_b": "169", "option_c": "196", "option_d": "225", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Find the next number in the series: 2, 6, 12, 20, 30, 42, ?", "option_a": "52", "option_b": "54", "option_c": "56", "option_d": "60", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Find the missing term in the alternating sequence: 7, 10, 8, 11, 9, 12, ?", "option_a": "7", "option_b": "10", "option_c": "13", "option_d": "14", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Look at the series: 1, 4, 27, 16, 125, 36, ?. What number comes next?", "option_a": "49", "option_b": "64", "option_c": "216", "option_d": "343", "correct_answer": "D", "difficulty": "HARD"},
    
    # Letter Series (6-10)
    {"section": "LOGICAL", "question_text": "Find the next letter in the increasing step series: C, F, J, O, U, ?", "option_a": "A", "option_b": "B", "option_c": "Z", "option_d": "Y", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Complete the paired series pattern: AZ, CX, EV, GT, ?", "option_a": "HS", "option_b": "IR", "option_c": "JQ", "option_d": "KP", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Find the missing term in the sequence: B2D, E5G, H8J, K11M, ?", "option_a": "N14P", "option_b": "M13O", "option_c": "N13P", "option_d": "O14Q", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Which letter group completes the pattern: BDF, HJL, NPR, ?", "option_a": "TVX", "option_b": "TUV", "option_c": "UWY", "option_d": "SUW", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "What is the next term in the series: ZW, TQ, NK, ?", "option_a": "HE", "option_b": "IF", "option_c": "JG", "option_d": "GD", "correct_answer": "A", "difficulty": "MEDIUM"},

    # Coding-Decoding (11-15)
    {"section": "LOGICAL", "question_text": "In a certain code, 'GLOBAL' is written as 'HMPCBN'. How is 'SERVER' written in that code?", "option_a": "TFUXFS", "option_b": "TFSWFS", "option_c": "SGTVES", "option_d": "TFRWFR", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "If 'CLOUD' is coded as 'DKPTE' using alternating (+1, -1, +1, -1, +1) shifts, how is 'STORM' coded?", "option_a": "TSPQN", "option_b": "TRPQN", "option_c": "USPRN", "option_d": "TSRQM", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "If 'CAT' is coded as 24 and 'DOG' is coded as 26, what is the value of 'BIRD'?", "option_a": "31", "option_b": "32", "option_c": "33", "option_d": "35", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "In a code language, 'ROBOT' is written as 'TQDOT'. How is 'CYBER' coded in the same pattern?", "option_a": "EACGT", "option_b": "EACER", "option_c": "EBDGR", "option_d": "FBDHS", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "If 'PYTHON' is written as 'NOHTYP' (reversed), how is 'DJANGO' written in the same code?", "option_a": "OGNAJD", "option_b": "OGNAJD", "option_c": "OGNAJD", "option_d": "OGNAJD", "correct_answer": "A", "difficulty": "EASY"},

    # Blood Relations (16-20)
    {"section": "LOGICAL", "question_text": "A is the brother of B. C is the father of A. D is the sister of E. E is the daughter of B. Who is the uncle of D?", "option_a": "A", "option_b": "C", "option_c": "B", "option_d": "E", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "If 'P + Q' means P is father of Q, and 'P * Q' means P is brother of Q, which expression shows that M is the uncle of N?", "option_a": "M * K + N", "option_b": "M + K * N", "option_c": "M - K + N", "option_d": "M * K - N", "correct_answer": "A", "difficulty": "HARD"},
    {"section": "LOGICAL", "question_text": "Pointing to a photograph, a woman says: 'He is the only son of my mother's only daughter.' How is the woman related to the boy?", "option_a": "Mother", "option_b": "Sister", "option_c": "Aunt", "option_d": "Grandmother", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Ravi is the son of Aman's father's sister. Sahil is the son of Divya, who is the mother of Gaurav and grandmother of Aman. How is Ravi related to Divya?", "option_a": "Son", "option_b": "Grandson", "option_c": "Nephew", "option_d": "Brother", "correct_answer": "B", "difficulty": "HARD"},
    {"section": "LOGICAL", "question_text": "Introducing a man, a woman says: 'His wife is the only daughter of my father.' How is the man related to the woman?", "option_a": "Brother", "option_b": "Husband", "option_c": "Father-in-law", "option_d": "Maternal Uncle", "correct_answer": "B", "difficulty": "EASY"},

    # Direction Sense (21-25)
    {"section": "LOGICAL", "question_text": "A delivery driver travels 12 km North, turns right and travels 5 km East. How far and in what direction is the driver from the starting point?", "option_a": "17 km North-East", "option_b": "13 km North-East", "option_c": "13 km North-West", "option_d": "15 km East", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Rohan walks 20m South, turns left and walks 15m, turns left again and walks 20m, then turns right and walks 10m. How far is he from his start?", "option_a": "25 meters East", "option_b": "35 meters East", "option_c": "25 meters North", "option_d": "15 meters South-East", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "A person is facing North-West. They turn 90 degrees clockwise, then 180 degrees counter-clockwise, and finally 90 degrees clockwise. Which direction are they facing now?", "option_a": "North-East", "option_b": "South-West", "option_c": "North-West", "option_d": "South-East", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Starting from point P, Priya walks 10 km North, turns left and walks 6 km, then turns right and walks 2 km. How far is she from line P-North?", "option_a": "6 km", "option_b": "8 km", "option_c": "10 km", "option_d": "12 km", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "One morning after sunrise, Suresh was standing facing a pole. The shadow of the pole fell exactly to his right. Which direction was he facing?", "option_a": "East", "option_b": "West", "option_c": "South", "option_d": "North", "correct_answer": "C", "difficulty": "HARD"},

    # Syllogisms (26-30)
    {"section": "LOGICAL", "question_text": "Statements: (1) All engineers are innovators. (2) Some innovators are writers. Conclusions: I. Some engineers are writers. II. Some innovators are engineers.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both conclusions follow", "option_d": "Neither conclusion follows", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Statements: (1) No cat is a dog. (2) All dogs are mammals. Conclusions: I. No cat is a mammal. II. Some mammals are dogs.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both conclusions follow", "option_d": "Neither conclusion follows", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Statements: (1) All laptops are computers. (2) All computers are electronic devices. Conclusions: I. All laptops are electronic devices. II. Some electronic devices are laptops.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both conclusions I and II follow", "option_d": "Neither conclusion follows", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Statements: (1) Some papers are books. (2) All books are libraries. Conclusions: I. Some papers are libraries. II. No paper is a library.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Either I or II follows", "option_d": "Neither follows", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Statements: (1) All keys are locks. (2) No lock is a door. Conclusions: I. No key is a door. II. Some doors are locks.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both follow", "option_d": "Neither follows", "correct_answer": "A", "difficulty": "EASY"},

    # Analogies (31-35)
    {"section": "LOGICAL", "question_text": "Complete the analogy: Thermometer : Temperature :: Barometer : ?", "option_a": "Humidity", "option_b": "Atmospheric Pressure", "option_c": "Wind Velocity", "option_d": "Earthquake Intensity", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Find the related number: 6 : 222 :: 7 : ?", "option_a": "343", "option_b": "350", "option_c": "352", "option_d": "356", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Complete the analogy: Odometer : Mileage :: Compass : ?", "option_a": "Speed", "option_b": "Altitude", "option_c": "Direction", "option_d": "Pressure", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Complete the analogy: Architect : Building :: Sculptor : ?", "option_a": "Museum", "option_b": "Statue", "option_c": "Stone", "option_d": "Chisel", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Find the related pair: 12 : 144 :: 15 : ?", "option_a": "210", "option_b": "225", "option_c": "240", "option_d": "250", "correct_answer": "B", "difficulty": "EASY"},

    # Odd One Out (36-40)
    {"section": "LOGICAL", "question_text": "Which of the following pairs is the odd one out: (8, 64), (6, 36), (7, 49), (9, 80)?", "option_a": "(8, 64)", "option_b": "(6, 36)", "option_c": "(7, 49)", "option_d": "(9, 80)", "correct_answer": "D", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Identify the odd one out among the materials: Copper, Zinc, Brass, Aluminum.", "option_a": "Copper", "option_b": "Zinc", "option_c": "Brass", "option_d": "Aluminum", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Find the odd one out among the storage media: RAM, ROM, Hard Disk, Cache Memory.", "option_a": "RAM", "option_b": "ROM", "option_c": "Hard Disk", "option_d": "Cache Memory", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Find the odd one out: 121, 169, 289, 324.", "option_a": "121", "option_b": "169", "option_c": "289", "option_d": "324", "correct_answer": "D", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Which word does not match the rest: Triangle, Rectangle, Square, Circle?", "option_a": "Triangle", "option_b": "Rectangle", "option_c": "Square", "option_d": "Circle", "correct_answer": "D", "difficulty": "EASY"},

    # Seating Arrangement (41-44)
    {"section": "LOGICAL", "question_text": "Six persons A, B, C, D, E, F sit in a circle facing the center. B is between A and C. E is between D and F. D is to the immediate left of A. Who is opposite to B?", "option_a": "D", "option_b": "E", "option_c": "F", "option_d": "C", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Five students P, Q, R, S, T sit in a row facing North. Q is to the immediate left of R and immediate right of P. S is to the right of R. T is on the extreme left. Who is in the middle?", "option_a": "P", "option_b": "Q", "option_c": "R", "option_d": "S", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "LOGICAL", "question_text": "Eight friends are seated in two parallel rows of 4 facing each other. Row 1 faces South, Row 2 faces North. A is opposite P. B is adjacent to A. Who faces Q if Q is adjacent to P?", "option_a": "B", "option_b": "C", "option_c": "D", "option_d": "Cannot be determined without more constraints", "correct_answer": "D", "difficulty": "HARD"},
    {"section": "LOGICAL", "question_text": "In a line of 25 people facing forward, Anuj is 8th from the front and Vikas is 10th from the back. How many people are standing between them?", "option_a": "6", "option_b": "7", "option_c": "8", "option_d": "9", "correct_answer": "B", "difficulty": "EASY"},

    # Logical Puzzles (45-47)
    {"section": "LOGICAL", "question_text": "Three developers Alice, Bob, Charlie code in Python, Java, Go (one each). Alice does not code in Java. The Python dev is not Bob. Charlie codes in Go. Which language does Bob code in?", "option_a": "Python", "option_b": "Java", "option_c": "Go", "option_d": "C++", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Among 4 boxes (Red, Blue, Green, Yellow), Red is heavier than Green, Blue is lighter than Yellow, Green is heavier than Yellow. Which box is the heaviest?", "option_a": "Red", "option_b": "Blue", "option_c": "Green", "option_d": "Yellow", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Five tasks T1, T2, T3, T4, T5 are scheduled on Monday through Friday. T2 is right before T4. T1 is on Monday. T5 is on Friday. On which day is T3 scheduled?", "option_a": "Tuesday", "option_b": "Wednesday", "option_c": "Thursday", "option_d": "Cannot be scheduled", "correct_answer": "A", "difficulty": "MEDIUM"},

    # Statement and Conclusion (48-50)
    {"section": "LOGICAL", "question_text": "Statement: 'To qualify for the tech lead interview, a candidate must have at least 5 years backend experience.' Conclusions: I. A candidate with 7 years is hired. II. A candidate with 3 years does not qualify.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both follow", "option_d": "Neither follows", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Statement: 'Company XYZ experienced a 40% growth in cloud service revenue after migrating to microservices.' Conclusions: I. Microservices guarantee revenue growth for any company. II. Cloud migration was beneficial for XYZ.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both follow", "option_d": "Neither follows", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "LOGICAL", "question_text": "Statement: 'Most high-performance engineering teams enforce automated unit and integration tests.' Conclusions: I. Writing tests is a common practice among high-performing teams. II. Teams without tests cannot write code.", "option_a": "Only Conclusion I follows", "option_b": "Only Conclusion II follows", "option_c": "Both follow", "option_d": "Neither follows", "correct_answer": "A", "difficulty": "EASY"},
]


# =========================================================================
# 2. QUANTITATIVE APTITUDE (50 Questions)
# =========================================================================
QUANTITATIVE_QUESTIONS: List[Dict[str, Any]] = [
    # Percentages (1-5)
    {"section": "QUANTITATIVE", "question_text": "If the price of a subscription increases by 25%, by what percentage must consumption be reduced so total expenditure remains unchanged?", "option_a": "20%", "option_b": "25%", "option_c": "16.67%", "option_d": "22.5%", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "In an exam, 40% of candidates failed in Coding, 30% in Aptitude, and 15% failed in both. What percentage passed in both sections?", "option_a": "45%", "option_b": "55%", "option_c": "50%", "option_d": "35%", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A number is increased by 20% and then decreased by 20%. What is the net percentage change?", "option_a": "No change", "option_b": "4% increase", "option_c": "4% decrease", "option_d": "2% decrease", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "If 60% of students in a class are boys and there are 24 girls, what is the total number of students in the class?", "option_a": "40", "option_b": "50", "option_c": "60", "option_d": "80", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A candidate secures 36% marks in an examination and fails by 18 marks. Another candidate secures 42% and gets 12 marks more than passing. What is the maximum marks?", "option_a": "400", "option_b": "500", "option_c": "600", "option_d": "700", "correct_answer": "B", "difficulty": "MEDIUM"},

    # Profit and Loss (6-10)
    {"section": "QUANTITATIVE", "question_text": "A vendor marks goods 40% above cost price and gives a discount of 20% on the marked price. What is the net profit percentage?", "option_a": "10%", "option_b": "12%", "option_c": "15%", "option_d": "20%", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "By selling an item for $450, a retailer incurs a 10% loss. At what selling price must it be sold to achieve a 20% profit?", "option_a": "$540", "option_b": "$580", "option_c": "$600", "option_d": "$650", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "If the cost price of 12 pens is equal to the selling price of 8 pens, what is the profit percentage?", "option_a": "33.33%", "option_b": "40%", "option_c": "50%", "option_d": "60%", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A trader gives two successive discounts of 10% and 20% on a list price of $500. What is the final selling price?", "option_a": "$350", "option_b": "$360", "option_c": "$380", "option_d": "$400", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A shopkeeper sells two items at $990 each, making a 10% profit on one and a 10% loss on the other. What is the overall net outcome?", "option_a": "No profit no loss", "option_b": "1% gain", "option_c": "1% loss", "option_d": "2% loss", "correct_answer": "C", "difficulty": "MEDIUM"},

    # Ratio and Proportion (11-14)
    {"section": "QUANTITATIVE", "question_text": "If A : B = 2 : 3 and B : C = 4 : 5, what is the ratio A : B : C?", "option_a": "8 : 12 : 15", "option_b": "6 : 9 : 15", "option_c": "8 : 10 : 15", "option_d": "2 : 4 : 5", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A bonus of $1,800 is divided among X, Y, and Z in the ratio 2 : 3 : 5. What is the share of Y?", "option_a": "$360", "option_b": "$540", "option_c": "$900", "option_d": "$600", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "The ratio of milk to water in a 40-liter mixture is 3 : 1. How much water must be added to make the ratio 2 : 1?", "option_a": "5 liters", "option_b": "6 liters", "option_c": "8 liters", "option_d": "10 liters", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "What is the third proportional to 9 and 12?", "option_a": "14", "option_b": "16", "option_c": "18", "option_d": "20", "correct_answer": "B", "difficulty": "EASY"},

    # Average (15-18)
    {"section": "QUANTITATIVE", "question_text": "The average weight of 8 team members increases by 1.5 kg when a member weighing 65 kg is replaced by a new recruit. What is the weight of the new recruit?", "option_a": "72 kg", "option_b": "75 kg", "option_c": "77 kg", "option_d": "80 kg", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A developer resolved an average of 45 tickets across 10 sprints. In the 11th sprint, they resolve 78 tickets. What is their new average?", "option_a": "46 tickets", "option_b": "47 tickets", "option_c": "48 tickets", "option_d": "50 tickets", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "The average of five consecutive even integers is 44. What is the largest of these integers?", "option_a": "46", "option_b": "48", "option_c": "50", "option_d": "52", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "In a company of 50 employees, the average salary is $4,000. If the manager's salary of $9,100 is included, what is the new average?", "option_a": "$4,050", "option_b": "$4,100", "option_c": "$4,150", "option_d": "$4,200", "correct_answer": "B", "difficulty": "MEDIUM"},

    # Time and Work (19-23)
    {"section": "QUANTITATIVE", "question_text": "Engineer A can complete a feature in 12 days and Engineer B in 24 days. Working together, in how many days will the feature be completed?", "option_a": "6 days", "option_b": "8 days", "option_c": "9 days", "option_d": "10 days", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "P can complete a job in 20 days and Q in 30 days. They work together for 6 days, and then P leaves. How many additional days will Q take to finish alone?", "option_a": "10 days", "option_b": "12 days", "option_c": "15 days", "option_d": "18 days", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "Pipe A fills a cistern in 4 hours, and Pipe B empties it in 6 hours. If both are opened together, in how many hours will the empty cistern fill?", "option_a": "8 hours", "option_b": "10 hours", "option_c": "12 hours", "option_d": "16 hours", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "12 workers can build a wall in 15 days working 8 hours a day. In how many days can 16 workers build the same wall working 6 hours a day?", "option_a": "12 days", "option_b": "15 days", "option_c": "18 days", "option_d": "20 days", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A is twice as efficient as B and together they finish a piece of work in 14 days. In how many days can A alone finish the work?", "option_a": "21 days", "option_b": "28 days", "option_c": "35 days", "option_d": "42 days", "correct_answer": "A", "difficulty": "MEDIUM"},

    # Time Speed Distance (24-28)
    {"section": "QUANTITATIVE", "question_text": "A train 240 meters long travels at 72 km/h. How many seconds will it take to completely pass a stationary signal pole?", "option_a": "10 seconds", "option_b": "12 seconds", "option_c": "14 seconds", "option_d": "16 seconds", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A car travels from City A to City B at 60 km/h and returns along the same route at 40 km/h. What is the average speed for the round trip?", "option_a": "48 km/h", "option_b": "50 km/h", "option_c": "52 km/h", "option_d": "45 km/h", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "Two trains 150m and 120m long are moving in opposite directions at 45 km/h and 63 km/h. How long will they take to completely pass each other?", "option_a": "7 seconds", "option_b": "8 seconds", "option_c": "9 seconds", "option_d": "10 seconds", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "Walking at 3/4 of his usual speed, a man reaches his office 20 minutes late. What is his usual travel time?", "option_a": "45 minutes", "option_b": "60 minutes", "option_c": "75 minutes", "option_d": "80 minutes", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A boat travels 24 km upstream in 6 hours and 24 km downstream in 3 hours. What is the speed of the current?", "option_a": "1 km/h", "option_b": "2 km/h", "option_c": "3 km/h", "option_d": "4 km/h", "correct_answer": "B", "difficulty": "MEDIUM"},

    # Simple Interest & Compound Interest (29-34)
    {"section": "QUANTITATIVE", "question_text": "A sum of $8,000 is invested at a simple interest rate of 7.5% per annum for 4 years. What is the total simple interest accrued?", "option_a": "$2,200", "option_b": "$2,400", "option_c": "$2,600", "option_d": "$2,800", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "A capital investment doubles itself in 8 years under simple interest. What is the annual rate of interest?", "option_a": "10%", "option_b": "12%", "option_c": "12.5%", "option_d": "15%", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "What is the compound interest earned on $15,000 for 2 years at 10% per annum, compounded annually?", "option_a": "$3,000", "option_b": "$3,150", "option_c": "$3,200", "option_d": "$3,300", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "The difference between CI and SI on a sum for 2 years at 8% per annum is $64. What is the principal sum?", "option_a": "$8,000", "option_b": "$10,000", "option_c": "$12,000", "option_d": "$15,000", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "At what rate percent per annum will $2,000 amount to $2,420 in 2 years compounded annually?", "option_a": "8%", "option_b": "10%", "option_c": "12%", "option_d": "15%", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A sum under compound interest amounts to $4,500 in 2 years and $6,750 in 4 years. What is the principal sum?", "option_a": "$2,500", "option_b": "$3,000", "option_c": "$3,200", "option_d": "$3,500", "correct_answer": "B", "difficulty": "HARD"},

    # Probability (35-39)
    {"section": "QUANTITATIVE", "question_text": "A bag contains 5 red, 4 green, and 3 blue balls. If a ball is drawn at random, what is the probability that it is NOT red?", "option_a": "5/12", "option_b": "7/12", "option_c": "1/2", "option_d": "1/3", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "Two fair 6-sided dice are rolled. What is the probability that the sum of the numbers showing on top is at least 10?", "option_a": "1/6", "option_b": "1/9", "option_c": "5/36", "option_d": "1/4", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A card is drawn from a well-shuffled pack of 52 cards. What is the probability of getting a King or a Spade?", "option_a": "4/13", "option_b": "16/52", "option_c": "1/4", "option_d": "17/52", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "If two fair coins are tossed simultaneously, what is the probability of obtaining at least one Head?", "option_a": "1/4", "option_b": "1/2", "option_c": "3/4", "option_d": "1", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "Three unbiased coins are tossed. What is the probability of getting exactly two Heads?", "option_a": "1/8", "option_b": "3/8", "option_c": "1/2", "option_d": "5/8", "correct_answer": "B", "difficulty": "EASY"},

    # Permutation and Combination (40-44)
    {"section": "QUANTITATIVE", "question_text": "In how many distinct ways can the letters of the word 'DESIGN' be arranged such that all the vowels always remain together?", "option_a": "120", "option_b": "240", "option_c": "360", "option_d": "720", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "From a team of 6 backend and 5 frontend engineers, in how many ways can a 4-person committee be formed with exactly 2 backend and 2 frontend engineers?", "option_a": "120", "option_b": "150", "option_c": "180", "option_d": "210", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "How many 3-digit numbers can be formed using the digits 1, 2, 3, 4, 5 without repetition?", "option_a": "20", "option_b": "60", "option_c": "120", "option_d": "125", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "In how many ways can 5 people be seated in a circle?", "option_a": "24", "option_b": "60", "option_c": "120", "option_d": "720", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "QUANTITATIVE", "question_text": "How many straight lines can be formed by joining 10 points in a plane, of which no 3 points are collinear?", "option_a": "20", "option_b": "45", "option_c": "90", "option_d": "100", "correct_answer": "B", "difficulty": "MEDIUM"},

    # Number System (45-47)
    {"section": "QUANTITATIVE", "question_text": "What is the greatest number that will divide 43, 91, and 183 so as to leave the same remainder in each case?", "option_a": "4", "option_b": "7", "option_c": "9", "option_d": "13", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "Find the unit digit of the expression (7^95 - 3^58).", "option_a": "0", "option_b": "4", "option_c": "6", "option_d": "7", "correct_answer": "B", "difficulty": "HARD"},
    {"section": "QUANTITATIVE", "question_text": "What is the least number which when divided by 6, 9, 12, 15, and 18 leaves remainder 2 in each case?", "option_a": "178", "option_b": "180", "option_c": "182", "option_d": "184", "correct_answer": "C", "difficulty": "MEDIUM"},

    # Ages (48-50)
    {"section": "QUANTITATIVE", "question_text": "The ratio of the present ages of a father and his son is 7 : 2. After 10 years, the ratio becomes 9 : 4. What is the father's present age?", "option_a": "28 years", "option_b": "35 years", "option_c": "42 years", "option_d": "49 years", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "Five years ago, the average age of A, B, C, and D was 45 years. With X joining them now, the average age of all five becomes 49 years. How old is X?", "option_a": "40 years", "option_b": "45 years", "option_c": "49 years", "option_d": "50 years", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "QUANTITATIVE", "question_text": "A mother is 4 times as old as her daughter. In 20 years, she will be twice as old as her daughter. What is the daughter's current age?", "option_a": "8 years", "option_b": "10 years", "option_c": "12 years", "option_d": "15 years", "correct_answer": "B", "difficulty": "EASY"},
]


# =========================================================================
# 3. TECHNICAL APTITUDE (50 Questions)
# =========================================================================
TECHNICAL_QUESTIONS: List[Dict[str, Any]] = [
    # Java (1-4)
    {"section": "TECHNICAL", "question_text": "In Java, what is the fundamental difference between the '==' operator and the '.equals()' method when comparing object references?", "option_a": "'==' compares memory addresses (reference equality), while '.equals()' compares object state/values", "option_b": "'==' compares values, while '.equals()' compares memory addresses", "option_c": "'==' can only be used on primitive types, while '.equals()' works on all types", "option_d": "Both perform identical bitwise comparisons", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which Java keyword prevents a class from being subclassed and a method from being overridden?", "option_a": "static", "option_b": "abstract", "option_c": "final", "option_d": "synchronized", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In Java memory management, where are objects instantiated with 'new' allocated?", "option_a": "Stack memory", "option_b": "Heap memory", "option_c": "Method area", "option_d": "Native registers", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What happens if a Java thread encounters an uncaught RuntimeException?", "option_a": "The entire JVM crashes immediately", "option_b": "Only the specific thread terminates and releases its locks", "option_c": "The thread is automatically restarted by the garbage collector", "option_d": "It causes a compilation error", "correct_answer": "B", "difficulty": "MEDIUM"},

    # Python (5-8)
    {"section": "TECHNICAL", "question_text": "What is the average time complexity of looking up a key in a Python dictionary (Hash Map)?", "option_a": "O(n)", "option_b": "O(log n)", "option_c": "O(1)", "option_d": "O(n log n)", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In Python, what is the key difference between a shallow copy (copy.copy) and a deep copy (copy.deepcopy)?", "option_a": "Shallow copy copies references to nested objects; deep copy recursively clones all nested objects", "option_b": "Shallow copy converts lists to tuples; deep copy retains mutability", "option_c": "Shallow copy is thread-safe; deep copy is asynchronous", "option_d": "There is no functional difference in Python 3", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "What is the primary role of the Global Interpreter Lock (GIL) in CPython?", "option_a": "To accelerate multi-threaded mathematical calculations", "option_b": "To ensure thread-safe memory management by allowing only one native thread to execute Python bytecode at a time", "option_c": "To prevent unauthorized socket connections", "option_d": "To optimize garbage collection cycles", "correct_answer": "B", "difficulty": "HARD"},
    {"section": "TECHNICAL", "question_text": "What does a Python function containing the 'yield' keyword return when initially called?", "option_a": "The first computed integer value", "option_b": "A generator iterator object", "option_c": "A standard tuple of all values", "option_d": "A coroutine future", "correct_answer": "B", "difficulty": "EASY"},

    # C / C++ (9-12)
    {"section": "TECHNICAL", "question_text": "In C++, what is the primary reason for declaring a base class destructor as 'virtual'?", "option_a": "To allow the destructor to take function arguments", "option_b": "To ensure derived class destructors are properly invoked when deleting through a base pointer", "option_c": "To prevent heap allocation of the base class", "option_d": "To force static linking during compilation", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "In C, which standard library function is used to dynamically reallocate an existing memory block without losing its data?", "option_a": "malloc()", "option_b": "calloc()", "option_c": "realloc()", "option_d": "free()", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In C++, what is a reference variable?", "option_a": "A pointer that can point to null", "option_b": "An alias for an already existing variable that cannot be reseated", "option_c": "A global variable accessible across translation units", "option_d": "A smart pointer allocated on the heap", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the output of 'sizeof(char)' guaranteed to be in the C standard?", "option_a": "1 byte", "option_b": "2 bytes", "option_c": "4 bytes", "option_d": "Architecture dependent", "correct_answer": "A", "difficulty": "EASY"},

    # OOP (13-16)
    {"section": "TECHNICAL", "question_text": "Which OOP principle allows a subclass to provide a specific implementation of a method defined in its superclass?", "option_a": "Encapsulation", "option_b": "Polymorphism / Method Overriding", "option_c": "Abstraction", "option_d": "Composition", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the OOP concept of restricting direct access to some of an object's components and bundling data with methods?", "option_a": "Encapsulation", "option_b": "Polymorphism", "option_c": "Inheritance", "option_d": "Coupling", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What design challenge in multiple inheritance is resolved by virtual base classes in C++?", "option_a": "The Thread Contention issue", "option_b": "The Diamond Problem (duplicate base subobjects)", "option_c": "The Stack Overflow error", "option_d": "Memory Fragmentation", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "In software design, what does the 'L' in SOLID principles represent?", "option_a": "Lazy Initialization Principle", "option_b": "Liskov Substitution Principle", "option_c": "Linear Flow Principle", "option_d": "Late Binding Principle", "correct_answer": "B", "difficulty": "MEDIUM"},

    # DBMS & SQL (17-21)
    {"section": "TECHNICAL", "question_text": "Which ACID property ensures that a transaction executes completely or rolls back entirely without partial state persistence?", "option_a": "Atomicity", "option_b": "Consistency", "option_c": "Isolation", "option_d": "Durability", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In SQL, which clause filters records AFTER an aggregate function (such as COUNT, SUM, AVG) has been computed with GROUP BY?", "option_a": "WHERE", "option_b": "HAVING", "option_c": "ORDER BY", "option_d": "LIMIT", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the primary objective of Database Normalization (1NF, 2NF, 3NF, BCNF)?", "option_a": "To increase storage utilization", "option_b": "To eliminate data redundancy and prevent insert/update/delete anomalies", "option_c": "To combine all database tables into a single denormalized structure", "option_d": "To remove the need for foreign keys", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What type of SQL JOIN returns all rows from the left table along with matched rows from the right table, filling nulls if no match exists?", "option_a": "INNER JOIN", "option_b": "LEFT OUTER JOIN", "option_c": "RIGHT OUTER JOIN", "option_d": "CROSS JOIN", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which standard index data structure is predominantly used in relational databases (MySQL, PostgreSQL) for range queries and fast lookups?", "option_a": "B+ Tree", "option_b": "Binary Search Tree", "option_c": "Trie", "option_d": "Red-Black Tree", "correct_answer": "A", "difficulty": "MEDIUM"},

    # Operating Systems (22-26)
    {"section": "TECHNICAL", "question_text": "Which of the following is NOT one of Coffman's four necessary conditions for a Deadlock in an Operating System?", "option_a": "Mutual Exclusion", "option_b": "Hold and Wait", "option_c": "Preemption Allowed", "option_d": "Circular Wait", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "What is the fundamental difference between a Process and a Thread in modern operating systems?", "option_a": "Processes share address space; threads have independent memory", "option_b": "Threads in the same process share heap memory and address space; processes have isolated memory spaces", "option_c": "Threads can only run in user space; processes run only in kernel space", "option_d": "Processes cannot have multiple threads of execution", "correct_answer": "B", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "What happens when a program accesses a virtual memory page that is not currently mapped into physical RAM?", "option_a": "Segmentation Fault", "option_b": "Page Fault", "option_c": "Deadlock", "option_d": "Kernel Panic", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which CPU scheduling algorithm is non-preemptive and selects the process with the shortest execution time next?", "option_a": "Round Robin", "option_b": "Shortest Job First (SJF)", "option_c": "Priority Preemptive", "option_d": "Multilevel Feedback Queue", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What mechanism does the OS use to prevent race conditions when multiple threads access shared critical sections?", "option_a": "Mutex / Semaphore", "option_b": "Virtual Memory Paging", "option_c": "DMA Controller", "option_d": "Instruction Pipelining", "correct_answer": "A", "difficulty": "EASY"},

    # Computer Networks (27-31)
    {"section": "TECHNICAL", "question_text": "At which layer of the OSI 7-layer model do routers operate and make IP path forwarding decisions?", "option_a": "Data Link Layer (Layer 2)", "option_b": "Network Layer (Layer 3)", "option_c": "Transport Layer (Layer 4)", "option_d": "Session Layer (Layer 5)", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which transport layer protocol provides connection-oriented, reliable byte-stream delivery with flow and congestion control?", "option_a": "UDP", "option_b": "TCP", "option_c": "ICMP", "option_d": "ARP", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the standard port number used for secure HTTPS web traffic?", "option_a": "80", "option_b": "8080", "option_c": "443", "option_d": "22", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In IPv4 networking, what is the default subnet mask for a standard Class C network?", "option_a": "255.0.0.0", "option_b": "255.255.0.0", "option_c": "255.255.255.0", "option_d": "255.255.255.255", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What protocol translates human-readable hostnames (e.g. google.com) into numerical IP addresses?", "option_a": "DHCP", "option_b": "DNS", "option_c": "FTP", "option_d": "SNMP", "correct_answer": "B", "difficulty": "EASY"},

    # Data Structures (32-36)
    {"section": "TECHNICAL", "question_text": "Which data structure follows a Last-In, First-Out (LIFO) access pattern?", "option_a": "Queue", "option_b": "Stack", "option_c": "Linked List", "option_d": "Binary Heap", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the time complexity to access an element by index in a contiguous dynamic array?", "option_a": "O(1)", "option_b": "O(n)", "option_c": "O(log n)", "option_d": "O(n^2)", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In a singly linked list with n nodes, what is the time complexity to insert a new node at the head (beginning)?", "option_a": "O(1)", "option_b": "O(n)", "option_c": "O(log n)", "option_d": "O(n log n)", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is the maximum number of children any node can have in a standard Binary Tree?", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "Arbitrary number", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which data structure is most efficient for implementing a Priority Queue?", "option_a": "Array", "option_b": "Singly Linked List", "option_c": "Binary Heap", "option_d": "Stack", "correct_answer": "C", "difficulty": "MEDIUM"},

    # Algorithms (37-41)
    {"section": "TECHNICAL", "question_text": "What is the worst-case time complexity of standard QuickSort when poor pivot choices occur on sorted input?", "option_a": "O(n)", "option_b": "O(n log n)", "option_c": "O(n^2)", "option_d": "O(log n)", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "What is the time complexity of Binary Search on a sorted array of size n?", "option_a": "O(1)", "option_b": "O(log n)", "option_c": "O(n)", "option_d": "O(n log n)", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which sorting algorithm offers a guaranteed O(n log n) time complexity in the worst case using a divide-and-conquer strategy?", "option_a": "Bubble Sort", "option_b": "Insertion Sort", "option_c": "Merge Sort", "option_d": "Selection Sort", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which algorithm is used to find the shortest path from a single source vertex to all other vertices in a weighted graph with non-negative edge weights?", "option_a": "Kruskal's Algorithm", "option_b": "Prim's Algorithm", "option_c": "Dijkstra's Algorithm", "option_d": "Floyd-Warshall", "correct_answer": "C", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "In Django ORM, which query method executes a SQL JOIN to optimize single-valued ForeignKey relationships and avoid N+1 queries?", "option_a": "prefetch_related()", "option_b": "select_related()", "option_c": "defer()", "option_d": "only()", "correct_answer": "B", "difficulty": "MEDIUM"},

    # HTML & CSS (42-46)
    {"section": "TECHNICAL", "question_text": "Which HTML5 semantic element is most appropriate for containing self-contained content intended for independent syndication (e.g. blog post)?", "option_a": "<div>", "option_b": "<section>", "option_c": "<article>", "option_d": "<aside>", "correct_answer": "C", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In the standard CSS Box Model, what is the correct order of layers from the outermost edge inward toward the text/media?", "option_a": "Margin -> Border -> Padding -> Content", "option_b": "Padding -> Margin -> Border -> Content", "option_c": "Border -> Margin -> Padding -> Content", "option_d": "Margin -> Padding -> Border -> Content", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In CSS Flexbox, which property aligns flex items along the main axis?", "option_a": "align-items", "option_b": "justify-content", "option_c": "align-content", "option_d": "flex-direction", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "Which meta tag is required in HTML5 responsive pages to control layout on mobile device screens?", "option_a": "<meta charset='UTF-8'>", "option_b": "<meta name='viewport' content='width=device-width, initial-scale=1.0'>", "option_c": "<meta http-equiv='X-UA-Compatible' content='IE=edge'>", "option_d": "<meta name='robots' content='index, follow'>", "correct_answer": "B", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "In CSS specificity, which selector has the highest precedence?", "option_a": "Type / Element selector (e.g. div)", "option_b": "Class selector (e.g. .btn)", "option_c": "ID selector (e.g. #header)", "option_d": "Universal selector (*)", "correct_answer": "C", "difficulty": "EASY"},

    # JavaScript (47-50)
    {"section": "TECHNICAL", "question_text": "In JavaScript, how do microtasks (Promises, queueMicrotask) interact with macrotasks (setTimeout, setInterval) in the Event Loop?", "option_a": "Microtasks and macrotasks run in random order", "option_b": "All pending microtasks are completely executed before the next macrotask is processed", "option_c": "Macrotasks always preempt microtasks", "option_d": "Microtasks only run when the window is blurred", "correct_answer": "B", "difficulty": "HARD"},
    {"section": "TECHNICAL", "question_text": "In JavaScript, what is the key difference between '==' and '===' comparison operators?", "option_a": "'==' performs type coercion before comparison; '===' checks both value and type without coercion", "option_b": "'===' performs type coercion; '==' checks reference equality", "option_c": "'===' is only valid for objects and arrays", "option_d": "There is no difference in modern ES6+", "correct_answer": "A", "difficulty": "EASY"},
    {"section": "TECHNICAL", "question_text": "What is a JavaScript Closure?", "option_a": "A function bundled together with references to its surrounding lexical environment", "option_b": "A method that terminates asynchronous event listeners", "option_c": "A syntax error that occurs when a block is unclosed", "option_d": "A native browser API to encrypt localStorage", "correct_answer": "A", "difficulty": "MEDIUM"},
    {"section": "TECHNICAL", "question_text": "In modern JavaScript (ES6+), what is the scoping difference between 'var' and 'let' / 'const'?", "option_a": "'var' is block-scoped; 'let' and 'const' are function-scoped", "option_b": "'var' is function-scoped; 'let' and 'const' are block-scoped", "option_c": "'let' cannot be reassigned; 'const' can be reassigned", "option_d": "They have identical scoping behavior", "correct_answer": "B", "difficulty": "EASY"},
]

# Total Combined 150 Questions
DEFAULT_QUESTIONS: List[Dict[str, Any]] = LOGICAL_QUESTIONS + QUANTITATIVE_QUESTIONS + TECHNICAL_QUESTIONS


def ensure_question_bank_seeded() -> int:
    """Ensure that all default questions are present in the database.

    Runs idempotently with update_or_create to prevent duplicates.
    Automatically synchronizes questions to Firestore if configured.
    Returns the total count of questions in the question bank.
    """
    from assessments.models import Question

    total_existing = Question.objects.count()
    if total_existing >= len(DEFAULT_QUESTIONS):
        return total_existing

    created_questions = []
    for q_data in DEFAULT_QUESTIONS:
        obj, created = Question.objects.update_or_create(
            section=q_data["section"],
            question_text=q_data["question_text"],
            defaults={
                "option_a": q_data["option_a"],
                "option_b": q_data["option_b"],
                "option_c": q_data["option_c"],
                "option_d": q_data["option_d"],
                "correct_answer": q_data["correct_answer"],
                "difficulty": q_data["difficulty"],
            },
        )
        if created:
            created_questions.append(obj)

    # Sync newly seeded questions to Firestore
    if created_questions:
        try:
            from services.firebase_service import bulk_sync_questions_to_firestore
            bulk_sync_questions_to_firestore(created_questions)
        except Exception as e:
            logger.warning("Failed to sync newly seeded questions to Firestore: %s", e)

    return Question.objects.count()
