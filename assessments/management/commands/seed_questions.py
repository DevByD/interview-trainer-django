from django.core.management.base import BaseCommand
from assessments.models import Question


QUESTIONS_DATA = [
    # -------------------------------------------------------------------------
    # LOGICAL REASONING (10 Questions)
    # -------------------------------------------------------------------------
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "Look at the sequence: 2, 6, 12, 20, 30, ?. What number should come next?",
        "option_a": "40",
        "option_b": "42",
        "option_c": "44",
        "option_d": "46",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "In a certain code, 'TRAIN' is written as 'WUDLQ'. How is 'BUS' written in that code?",
        "option_a": "EXV",
        "option_b": "DWV",
        "option_c": "EYW",
        "option_d": "DXV",
        "correct_answer": "A",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "Pointing to a photograph, a man said: 'She is the daughter of my grandfather's only son.' How is the woman related to the man?",
        "option_a": "Mother",
        "option_b": "Aunt",
        "option_c": "Sister",
        "option_d": "Daughter",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "Statements: (1) All birds have feathers. (2) All penguins are birds. Conclusions: I. Penguins have feathers. II. All feathered creatures are penguins.",
        "option_a": "Only Conclusion I follows",
        "option_b": "Only Conclusion II follows",
        "option_c": "Both conclusions follow",
        "option_d": "Neither conclusion follows",
        "correct_answer": "A",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "Find the odd one out from the following group: Iron, Silver, Gold, Mercury, Platinum.",
        "option_a": "Iron",
        "option_b": "Mercury",
        "option_c": "Gold",
        "option_d": "Platinum",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "Five friends P, Q, R, S, and T sit in a line facing North. Q sits between P and T. S is not at either end. If P is at the extreme left, who is in the middle?",
        "option_a": "P",
        "option_b": "Q",
        "option_c": "R",
        "option_d": "T",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "If Monday falls on the 1st of a 30-day month, how many Mondays and Tuesdays will occur in that month?",
        "option_a": "5 Mondays, 4 Tuesdays",
        "option_b": "5 Mondays, 5 Tuesdays",
        "option_c": "4 Mondays, 5 Tuesdays",
        "option_d": "4 Mondays, 4 Tuesdays",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "If '+' means multiplication, '-' means division, '*' means addition, and '/' means subtraction, what is the value of: 20 + 5 - 10 * 6 / 4?",
        "option_a": "12",
        "option_b": "16",
        "option_c": "8",
        "option_d": "10",
        "correct_answer": "A",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "A clock shows 3:30. What is the acute angle between the hour hand and the minute hand?",
        "option_a": "70 degrees",
        "option_b": "75 degrees",
        "option_c": "80 degrees",
        "option_d": "90 degrees",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.HARD,
    },
    {
        "section": Question.Sections.LOGICAL,
        "question_text": "If in a truth-table system: P implies Q is False, what can be deduced about the truth values of P and Q?",
        "option_a": "P is True, Q is True",
        "option_b": "P is False, Q is True",
        "option_c": "P is True, Q is False",
        "option_d": "P is False, Q is False",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.HARD,
    },

    # -------------------------------------------------------------------------
    # QUANTITATIVE APTITUDE (10 Questions)
    # -------------------------------------------------------------------------
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "If an item is purchased for $80 and sold for $100, what is the percentage profit?",
        "option_a": "20%",
        "option_b": "25%",
        "option_c": "30%",
        "option_d": "15%",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "What is the average of the first five prime numbers (2, 3, 5, 7, 11)?",
        "option_a": "5.6",
        "option_b": "5.4",
        "option_c": "5.8",
        "option_d": "6.0",
        "correct_answer": "A",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "A car travels 180 km in 3 hours. What is its speed in meters per second?",
        "option_a": "15 m/s",
        "option_b": "16.67 m/s",
        "option_c": "20 m/s",
        "option_d": "25 m/s",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "The ratio of two numbers is 3:5 and their sum is 160. What is the larger number?",
        "option_a": "60",
        "option_b": "80",
        "option_c": "100",
        "option_d": "120",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "Pipe A can fill a tank in 6 hours, and Pipe B can fill it in 12 hours. How long will they take working together?",
        "option_a": "3 hours",
        "option_b": "4 hours",
        "option_c": "5 hours",
        "option_d": "4.5 hours",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "A sum of $5,000 earns simple interest of $600 in 2 years. What is the annual rate of interest?",
        "option_a": "5%",
        "option_b": "6%",
        "option_c": "8%",
        "option_d": "10%",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "In how many distinct ways can the letters of the word 'LEADER' be arranged?",
        "option_a": "720",
        "option_b": "360",
        "option_c": "120",
        "option_d": "180",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "Two dice are rolled simultaneously. What is the probability of getting a sum of 9?",
        "option_a": "1/6",
        "option_b": "1/9",
        "option_c": "1/12",
        "option_d": "5/36",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "A train 150 meters long passes a platform 250 meters long in 20 seconds. What is the train's speed in km/h?",
        "option_a": "60 km/h",
        "option_b": "72 km/h",
        "option_c": "80 km/h",
        "option_d": "90 km/h",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.HARD,
    },
    {
        "section": Question.Sections.QUANTITATIVE,
        "question_text": "The compound interest on $10,000 for 2 years at 10% per annum compounded annually is:",
        "option_a": "$2,000",
        "option_b": "$2,100",
        "option_c": "$2,200",
        "option_d": "$2,050",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.HARD,
    },

    # -------------------------------------------------------------------------
    # TECHNICAL APTITUDE (10 Questions)
    # -------------------------------------------------------------------------
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "What is the average time complexity of looking up a key in a Python dictionary / Hash Map?",
        "option_a": "O(n)",
        "option_b": "O(log n)",
        "option_c": "O(1)",
        "option_d": "O(n log n)",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "Which HTTP status code represents 'Resource Created Successfully'?",
        "option_a": "200 OK",
        "option_b": "201 Created",
        "option_c": "204 No Content",
        "option_d": "301 Moved Permanently",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "In SQL, which clause is used to filter records after an aggregate function (GROUP BY) has been applied?",
        "option_a": "WHERE",
        "option_b": "HAVING",
        "option_c": "ORDER BY",
        "option_d": "LIMIT",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "Which of the following data structures operates on a Last In First Out (LIFO) basis?",
        "option_a": "Queue",
        "option_b": "Stack",
        "option_c": "Linked List",
        "option_d": "Heap",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "In Python, which of the following is an immutable data type?",
        "option_a": "List",
        "option_b": "Dictionary",
        "option_c": "Tuple",
        "option_d": "Set",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.EASY,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "What is the primary purpose of database normalization?",
        "option_a": "To increase storage space used",
        "option_b": "To eliminate data redundancy and prevent anomalies",
        "option_c": "To merge all tables into a single table",
        "option_d": "To avoid using primary keys",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "In object-oriented programming, which principle allows a subclass to provide a specific implementation of a method defined in its superclass?",
        "option_a": "Encapsulation",
        "option_b": "Polymorphism / Method Overriding",
        "option_c": "Abstraction",
        "option_d": "Composition",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "What is the worst-case time complexity of standard QuickSort algorithm?",
        "option_a": "O(n)",
        "option_b": "O(n log n)",
        "option_c": "O(n^2)",
        "option_d": "O(log n)",
        "correct_answer": "C",
        "difficulty": Question.Difficulties.MEDIUM,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "In Django ORM, which method is best suited to prevent N+1 query problems on Foreign Key relationships?",
        "option_a": "prefetch_related()",
        "option_b": "select_related()",
        "option_c": "defer()",
        "option_d": "only()",
        "correct_answer": "B",
        "difficulty": Question.Difficulties.HARD,
    },
    {
        "section": Question.Sections.TECHNICAL,
        "question_text": "Which ACID property ensures that a transaction is completely executed or completely rolled back without partial states?",
        "option_a": "Atomicity",
        "option_b": "Consistency",
        "option_c": "Isolation",
        "option_d": "Durability",
        "correct_answer": "A",
        "difficulty": Question.Difficulties.HARD,
    },
]


class Command(BaseCommand):
    help = "Seed question bank with 10 Logical, 10 Quantitative, and 10 Technical aptitude questions."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for q_data in QUESTIONS_DATA:
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
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Question bank seeded successfully! Created: {created_count}, Updated: {updated_count}. Total in bank: {Question.objects.count()}"
            )
        )
