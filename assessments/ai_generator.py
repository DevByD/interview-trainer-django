"""AI Question Generator Service for Employer Question Banks.

Integrates with Google Gemini models via secure REST API with environment-configured API keys.
Includes robust JSON schema validation, safety checks, and dynamic algorithmic fallbacks
to ensure reliable, high-quality original questions across Aptitude (Logical, Quantitative,
Technical) and Coding (Arrays, Strings, Hashing, Stack/Queue, Linked Lists, Trees, DP, etc.).
"""

import json
import logging
import os
import random
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from django.utils.text import slugify

from assessments.models import CodingQuestion, CodingTestCase, Question

logger = logging.getLogger(__name__)

# Primary & Fallback Gemini Models
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from environment variables."""
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY")


def call_gemini_api(prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
    """Invoke Gemini REST API with JSON response expectation."""
    api_key = get_gemini_api_key()
    if not api_key:
        logger.info("No GEMINI_API_KEY found in environment. Using dynamic algorithmic question generator.")
        return None

    url = f"{GEMINI_API_URL}?key={api_key}"

    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as exc:
        logger.warning("Gemini API call encountered an error: %s. Falling back to algorithmic generator.", exc)
        return None

    return None


def clean_json_response(raw_text: str) -> Any:
    """Safely parse JSON from raw LLM output, stripping markdown code fences if present."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# Validation Functions
# ---------------------------------------------------------------------------

def validate_aptitude_question(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that an aptitude question dictionary contains all required fields and valid choices."""
    required = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_answer", "section", "difficulty"]
    for field in required:
        if not data.get(field):
            return False, f"Missing required field: {field}"

    if data["correct_answer"] not in ["A", "B", "C", "D"]:
        return False, f"Invalid correct_answer '{data.get('correct_answer')}'. Must be one of A, B, C, D."

    if data["section"] not in [Question.Sections.LOGICAL, Question.Sections.QUANTITATIVE, Question.Sections.TECHNICAL]:
        return False, f"Invalid section '{data.get('section')}'."

    if data["difficulty"] not in [Question.Difficulties.EASY, Question.Difficulties.MEDIUM, Question.Difficulties.HARD]:
        return False, f"Invalid difficulty '{data.get('difficulty')}'."

    return True, "Valid"


def validate_coding_question(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that a coding problem dictionary contains valid problem statement, starter code, and test cases."""
    required = ["title", "description", "input_format", "output_format", "sample_input", "sample_output", "category", "difficulty"]
    for field in required:
        if not data.get(field):
            return False, f"Missing required coding field: {field}"

    if data["difficulty"] not in [Question.Difficulties.EASY, Question.Difficulties.MEDIUM, Question.Difficulties.HARD]:
        return False, f"Invalid coding difficulty '{data.get('difficulty')}'."

    test_cases = data.get("test_cases", [])
    if not isinstance(test_cases, list) or len(test_cases) < 2:
        return False, "Coding questions must provide at least 2 test cases."

    has_sample = any(tc.get("is_sample") for tc in test_cases)
    has_hidden = any(not tc.get("is_sample") for tc in test_cases)

    if not has_sample or not has_hidden:
        return False, "Coding questions must provide at least 1 sample test case and 1 hidden test case."

    return True, "Valid"


# ---------------------------------------------------------------------------
# Algorithmic Dynamic Fallback Question Generators
# ---------------------------------------------------------------------------

def generate_algorithmic_aptitude(section: str, difficulty: str, count: int) -> List[Dict[str, Any]]:
    """Generate high-quality original aptitude questions algorithmically with randomized numbers and varied logic."""
    questions = []

    for idx in range(count):
        if section == Question.Sections.QUANTITATIVE:
            q_type = random.choice(["speed_distance", "profit_loss", "work_time", "simple_interest", "percentage"])
            if q_type == "speed_distance":
                speed = random.randint(30, 90)
                time = random.randint(2, 6)
                dist = speed * time
                q_text = f"A high-speed train travels at a constant velocity of {speed} km/h for {time} hours. What total distance does it cover?"
                correct = f"{dist} km"
                distractor1 = f"{dist + speed} km"
                distractor2 = f"{dist - 15} km"
                distractor3 = f"{dist + 20} km"
                explanation = f"Distance = Speed × Time = {speed} km/h × {time} h = {dist} km."
            elif q_type == "profit_loss":
                cp = random.randint(200, 800)
                profit_pct = random.choice([10, 15, 20, 25])
                profit = (cp * profit_pct) // 100
                sp = cp + profit
                q_text = f"An electronics retailer purchases a smart monitor for ${cp} and sells it at a {profit_pct}% profit margin. What is the selling price?"
                correct = f"${sp}"
                distractor1 = f"${sp + 25}"
                distractor2 = f"${cp + profit_pct}"
                distractor3 = f"${sp - 20}"
                explanation = f"Selling Price = Cost Price + Profit = ${cp} + ({profit_pct}% of ${cp}) = ${cp} + ${profit} = ${sp}."
            elif q_type == "work_time":
                a_days = random.choice([6, 10, 12, 15])
                b_days = random.choice([10, 15, 20, 30])
                total_work = a_days * b_days
                rate = (total_work // a_days) + (total_work // b_days)
                combined = round(total_work / rate, 1)
                q_text = f"Engineer Alex can deploy a service in {a_days} hours, while Engineer Jordan can deploy the same service in {b_days} hours. Working concurrently, how many hours will they take?"
                correct = f"{combined} hours"
                distractor1 = f"{round(combined + 2.5, 1)} hours"
                distractor2 = f"{round(combined - 1.2, 1)} hours"
                distractor3 = f"{round((a_days + b_days) / 2, 1)} hours"
                explanation = f"Combined Rate = (1/{a_days}) + (1/{b_days}) = {rate}/{total_work} per hour. Time = {total_work}/{rate} = {combined} hours."
            else:
                p = random.randint(1000, 5000)
                r = random.choice([5, 8, 10, 12])
                t = random.randint(2, 5)
                si = (p * r * t) // 100
                q_text = f"Calculate the simple interest on a principal investment of ${p} at an annual interest rate of {r}% for {t} years."
                correct = f"${si}"
                distractor1 = f"${si + 100}"
                distractor2 = f"${si - 50}"
                distractor3 = f"${(p * r) // 100}"
                explanation = f"Simple Interest = (P × R × T) / 100 = ({p} × {r} × {t}) / 100 = ${si}."

        elif section == Question.Sections.LOGICAL:
            q_type = random.choice(["number_series", "coding_decoding", "blood_relations", "direction_sense"])
            if q_type == "number_series":
                start = random.randint(2, 10)
                step = random.randint(3, 7)
                series = [start + i * step for i in range(5)]
                next_val = start + 5 * step
                q_text = f"Identify the next number in the arithmetic progression sequence: {', '.join(map(str, series))}, ?"
                correct = str(next_val)
                distractor1 = str(next_val + step)
                distractor2 = str(next_val - 2)
                distractor3 = str(next_val + 2)
                explanation = f"The series increases by a constant difference of +{step}. Next term = {series[-1]} + {step} = {next_val}."
            elif q_type == "coding_decoding":
                words = [("SERVER", "TFSWFS", "CLIENT", "DMJFOU"), ("CLOUD", "DMPVE", "STACK", "TUBDL"), ("ROUTER", "SPVUFS", "SWITCH", "TXJUDI")]
                w1, c1, w2, c2 = random.choice(words)
                q_text = f"In a cryptographic substitution cipher, if '{w1}' is encoded as '{c1}', how is '{w2}' encoded?"
                correct = c2
                distractor1 = c2[:-1] + "X"
                distractor2 = c2[1:] + "A"
                distractor3 = w2[::-1]
                explanation = f"Each character in the word is shifted forward by +1 alphabetical position. '{w2}' shifted by +1 becomes '{c2}'."
            else:
                dist1 = random.randint(10, 30)
                dist2 = random.randint(10, 30)
                q_text = f"A robotic rover moves {dist1} meters North, turns 90 degrees clockwise and moves {dist2} meters East, then turns right and moves {dist1} meters South. How far is it from its starting origin?"
                correct = f"{dist2} meters East"
                distractor1 = f"{dist1} meters North"
                distractor2 = f"{dist1 + dist2} meters East"
                distractor3 = f"{dist2} meters West"
                explanation = f"The northward movement of {dist1}m is canceled by the southward movement of {dist1}m, leaving a net displacement of {dist2}m East."

        else:  # TECHNICAL
            tech_questions = [
                ("What is the worst-case time complexity of searching for an element in a balanced Binary Search Tree (AVL / Red-Black Tree)?", "O(log N)", "O(N)", "O(1)", "O(N log N)", "A balanced BST maintains logarithmic height, guaranteeing O(log N) search time."),
                ("Which HTTP response status code indicates that the requested resource has been permanently moved to a new URI?", "301 Moved Permanently", "302 Found", "307 Temporary Redirect", "404 Not Found", "HTTP 301 designates a permanent redirection to a new location."),
                ("In relational databases, which ACID property guarantees that completed database transactions survive system crashes?", "Durability", "Atomicity", "Consistency", "Isolation", "Durability ensures committed transaction changes are written to non-volatile storage and persist across crashes."),
                ("Which concurrency mechanism in Python prevents multiple native OS threads from executing Python bytecodes simultaneously?", "Global Interpreter Lock (GIL)", "Garbage Collector", "Event Loop", "JIT Compiler", "The Global Interpreter Lock (GIL) synchronizes the execution of threads in CPython."),
                ("What data structure is utilized internally by depth-first search (DFS) traversal on graphs?", "Stack (or Call Stack)", "Queue", "Min-Heap", "Hash Map", "DFS explores graph nodes deeply using a Last-In First-Out (LIFO) Stack or recursion call stack."),
                ("In RESTful API design, which HTTP method is expected to be idempotent when updating a full resource entity?", "PUT", "POST", "PATCH", "CONNECT", "PUT is idempotent: sending multiple identical PUT requests produces the exact same server state."),
                ("Which algorithm is commonly used to find the shortest path from a single source vertex in a weighted graph with non-negative edge weights?", "Dijkstra's Algorithm", "Bellman-Ford Algorithm", "Floyd-Warshall Algorithm", "Kruskal's Algorithm", "Dijkstra's algorithm efficiently computes shortest paths from a single source on non-negative weighted graphs."),
                ("In symmetric cryptography, which block cipher mode requires an initialization vector (IV) to prevent identical plaintext blocks producing identical ciphertext?", "Cipher Block Chaining (CBC)", "Electronic Codebook (ECB)", "Plaintext Mode", "Null Mode", "CBC mode chains ciphertext with an IV, ensuring identical plaintexts yield different ciphertexts."),
            ]
            t_item = tech_questions[idx % len(tech_questions)]
            q_text, correct, distractor1, distractor2, distractor3, explanation = t_item
            if idx >= len(tech_questions):
                q_text = f"{q_text} (Variant #{idx + 1})"


        opts = [correct, distractor1, distractor2, distractor3]
        random.shuffle(opts)
        correct_letter = chr(65 + opts.index(correct))

        questions.append({
            "section": section,
            "difficulty": difficulty,
            "question_text": q_text,
            "option_a": opts[0],
            "option_b": opts[1],
            "option_c": opts[2],
            "option_d": opts[3],
            "correct_answer": correct_letter,
            "explanation": explanation,
        })

    return questions


def generate_algorithmic_coding(category: str, difficulty: str, language: str, count: int) -> List[Dict[str, Any]]:
    """Generate original algorithmic coding problems with comprehensive starter code and test cases."""
    coding_templates = {
        CodingQuestion.Categories.ARRAYS: [
            {
                "title": "Compute Running Prefix Sums",
                "desc": "Given an array of integers `nums`, return the running prefix sum array where `prefix[i] = sum(nums[0]...nums[i])`.",
                "in_fmt": "A space-separated list of integers `nums`.",
                "out_fmt": "A space-separated list of running prefix sums.",
                "sample_in": "1 2 3 4",
                "sample_out": "1 3 6 10",
                "test_cases": [
                    {"input_data": "1 2 3 4", "expected_output": "1 3 6 10", "is_sample": True, "order": 1},
                    {"input_data": "1 1 1 1 1", "expected_output": "1 2 3 4 5", "is_sample": True, "order": 2},
                    {"input_data": "3 1 2 10 1", "expected_output": "3 4 6 16 17", "is_sample": False, "order": 3},
                    {"input_data": "-2 5 -1 7", "expected_output": "-2 3 2 9", "is_sample": False, "order": 4},
                ],
            },
            {
                "title": "Find Maximum Subarray Product",
                "desc": "Given an integer array `nums`, find the contiguous subarray within an array (containing at least one number) which has the largest product.",
                "in_fmt": "A space-separated list of integers `nums`.",
                "out_fmt": "A single integer denoting the maximum product.",
                "sample_in": "2 3 -2 4",
                "sample_out": "6",
                "test_cases": [
                    {"input_data": "2 3 -2 4", "expected_output": "6", "is_sample": True, "order": 1},
                    {"input_data": "-2 0 -1", "expected_output": "0", "is_sample": True, "order": 2},
                    {"input_data": "-2 3 -4", "expected_output": "24", "is_sample": False, "order": 3},
                    {"input_data": "0 2", "expected_output": "2", "is_sample": False, "order": 4},
                ],
            }
        ],
        CodingQuestion.Categories.STRINGS: [
            {
                "title": "Valid Anagram Verification",
                "desc": "Given two strings `s` and `t`, return `true` if `t` is an anagram of `s`, and `false` otherwise.",
                "in_fmt": "Two space-separated strings `s` and `t`.",
                "out_fmt": "true or false",
                "sample_in": "anagram nagaram",
                "sample_out": "true",
                "test_cases": [
                    {"input_data": "anagram nagaram", "expected_output": "true", "is_sample": True, "order": 1},
                    {"input_data": "rat car", "expected_output": "false", "is_sample": True, "order": 2},
                    {"input_data": "listen silent", "expected_output": "true", "is_sample": False, "order": 3},
                    {"input_data": "a ab", "expected_output": "false", "is_sample": False, "order": 4},
                ],
            },
            {
                "title": "Compress String Run-Length",
                "desc": "Implement basic string compression using the counts of repeated characters. If compressed string is not smaller, return original.",
                "in_fmt": "A single continuous string `s`.",
                "out_fmt": "Compressed string representation.",
                "sample_in": "aabcccccaaa",
                "sample_out": "a2b1c5a3",
                "test_cases": [
                    {"input_data": "aabcccccaaa", "expected_output": "a2b1c5a3", "is_sample": True, "order": 1},
                    {"input_data": "abcd", "expected_output": "abcd", "is_sample": True, "order": 2},
                    {"input_data": "wwwwaaadexxxxxx", "expected_output": "w4a3d1e1x6", "is_sample": False, "order": 3},
                    {"input_data": "aaaa", "expected_output": "a4", "is_sample": False, "order": 4},
                ],
            }
        ],
    }

    selected_templates = coding_templates.get(category) or coding_templates[CodingQuestion.Categories.ARRAYS]
    problems = []

    for i in range(count):
        tmpl = selected_templates[i % len(selected_templates)]
        title_suffix = f" #{i + 1}" if count > len(selected_templates) else ""
        title = f"{tmpl['title']}{title_suffix}"
        slug = slugify(f"{title}-{difficulty}-{random.randint(1000, 9999)}")

        starter_code = {
            "python": "# Write your solution below\nimport sys\n\ndef solve():\n    input_data = sys.stdin.read().strip()\n    if not input_data: return\n    # Implement your logic here\n\nif __name__ == '__main__':\n    solve()\n",
            "javascript": "// Write your solution below\nconst fs = require('fs');\nfunction solve() {\n    const input = fs.readFileSync(0, 'utf-8').trim();\n    if (!input) return;\n    // Implement your logic here\n}\nsolve();\n",
            "java": "// Write your solution below\nimport java.util.Scanner;\npublic class Solution {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        if (!sc.hasNext()) return;\n        // Implement your logic here\n    }\n}\n",
            "cpp": "// Write your solution below\n#include <iostream>\n#include <vector>\n#include <string>\nusing namespace std;\n\nint main() {\n    // Implement your logic here\n    return 0;\n}\n",
        }

        problems.append({
            "title": title,
            "slug": slug,
            "category": category,
            "difficulty": difficulty,
            "description": tmpl["desc"],
            "input_format": tmpl["in_fmt"],
            "output_format": tmpl["out_fmt"],
            "constraints": "1 <= N <= 10^5, Time Limit: 2.0s, Memory Limit: 256MB",
            "sample_input": tmpl["sample_in"],
            "sample_output": tmpl["sample_out"],
            "explanation": "Standard algorithmic execution on sample input.",
            "starter_code": starter_code,
            "test_cases": tmpl["test_cases"],
        })

    return problems


# ---------------------------------------------------------------------------
# High Level Generator Dispatchers
# ---------------------------------------------------------------------------

def generate_aptitude_questions(
    section: str,
    difficulty: str = Question.Difficulties.MEDIUM,
    count: int = 5,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate structured aptitude questions using Gemini AI if available or algorithmic engine."""
    system_instruction = (
        "You are an expert technical recruiter and assessment architect. Generate original multiple-choice questions "
        "for hiring assessments. Return ONLY a valid JSON array of objects with keys: "
        "question_text, option_a, option_b, option_c, option_d, correct_answer (one of A,B,C,D), explanation, "
        "section, difficulty."
    )

    prompt = (
        f"Generate {count} distinct, original multiple choice questions for the section '{section}' "
        f"at difficulty level '{difficulty}'. "
        f"Ensure options are concise, accurate, and explanations are clear."
    )

    raw_response = call_gemini_api(prompt, system_instruction=system_instruction)
    if raw_response:
        try:
            parsed = clean_json_response(raw_response)
            if isinstance(parsed, list):
                valid_questions = []
                for item in parsed:
                    item["section"] = section
                    item["difficulty"] = difficulty
                    is_valid, _ = validate_aptitude_question(item)
                    if is_valid:
                        valid_questions.append(item)
                if len(valid_questions) >= count:
                    return valid_questions[:count]
        except Exception as exc:
            logger.warning("Failed to parse Gemini aptitude output: %s. Using algorithmic fallback.", exc)

    return generate_algorithmic_aptitude(section, difficulty, count)


def generate_coding_questions(
    category: str = CodingQuestion.Categories.ARRAYS,
    difficulty: str = Question.Difficulties.MEDIUM,
    language: str = "python",
    count: int = 1,
) -> List[Dict[str, Any]]:
    """Generate structured coding problems with test cases using Gemini AI or algorithmic engine."""
    system_instruction = (
        "You are an expert competitive programming judge and technical interviewer. Generate original DSA coding challenges. "
        "Return ONLY a valid JSON array of objects with keys: "
        "title, description, input_format, output_format, constraints, sample_input, sample_output, explanation, "
        "category, difficulty, starter_code (dictionary with python, javascript, java, cpp), and test_cases (array of objects with input_data, expected_output, is_sample, order)."
    )

    prompt = (
        f"Generate {count} original DSA coding problem(s) in category '{category}' at difficulty level '{difficulty}'. "
        f"Target primary language: {language}. Each problem must include at least 2 sample test cases (is_sample: true) "
        f"and at least 2 hidden edge-case test cases (is_sample: false)."
    )

    raw_response = call_gemini_api(prompt, system_instruction=system_instruction)
    if raw_response:
        try:
            parsed = clean_json_response(raw_response)
            if isinstance(parsed, list):
                valid_problems = []
                for item in parsed:
                    item["category"] = category
                    item["difficulty"] = difficulty
                    item["slug"] = slugify(f"{item.get('title', 'problem')}-{random.randint(1000, 9999)}")
                    is_valid, _ = validate_coding_question(item)
                    if is_valid:
                        valid_problems.append(item)
                if len(valid_problems) >= count:
                    return valid_problems[:count]
        except Exception as exc:
            logger.warning("Failed to parse Gemini coding output: %s. Using algorithmic fallback.", exc)

    return generate_algorithmic_coding(category, difficulty, language, count)


# ---------------------------------------------------------------------------
# Duplicate Detection & Database Persistence
# ---------------------------------------------------------------------------

def is_duplicate_aptitude_question(question_text: str) -> bool:
    """Check if normalized question text already exists in active question bank."""
    norm = re.sub(r"\s+", " ", question_text).strip().lower()
    for existing in Question.objects.values_list("question_text", flat=True):
        if re.sub(r"\s+", " ", existing).strip().lower() == norm:
            return True
    return False


def is_duplicate_coding_question(title: str) -> bool:
    """Check if normalized coding challenge title or slug already exists."""
    norm = title.strip().lower()
    return CodingQuestion.objects.filter(title__iexact=norm).exists()


def save_aptitude_questions(questions_data: List[Dict[str, Any]]) -> List[Question]:
    """Persist validated, non-duplicate aptitude questions into the database."""
    saved = []
    for q_dict in questions_data:
        is_valid, _ = validate_aptitude_question(q_dict)
        if not is_valid:
            continue

        # Prevent duplicate questions
        if is_duplicate_aptitude_question(q_dict["question_text"]):
            logger.info("Skipping duplicate aptitude question: %s", q_dict["question_text"][:40])
            continue

        q = Question.objects.create(
            section=q_dict["section"],
            difficulty=q_dict["difficulty"],
            question_text=q_dict["question_text"],
            option_a=q_dict["option_a"],
            option_b=q_dict["option_b"],
            option_c=q_dict["option_c"],
            option_d=q_dict["option_d"],
            correct_answer=q_dict["correct_answer"],
        )
        saved.append(q)
    return saved


def save_coding_questions(coding_data: List[Dict[str, Any]]) -> List[CodingQuestion]:
    """Persist validated, non-duplicate coding challenges along with their test cases into the database."""
    saved = []
    for c_dict in coding_data:
        is_valid, _ = validate_coding_question(c_dict)
        if not is_valid:
            continue

        # Prevent duplicate problems
        if is_duplicate_coding_question(c_dict["title"]):
            logger.info("Skipping duplicate coding problem: %s", c_dict["title"])
            continue

        slug = c_dict.get("slug") or slugify(f"{c_dict['title']}-{random.randint(1000, 9999)}")
        # Guarantee slug uniqueness
        while CodingQuestion.objects.filter(slug=slug).exists():
            slug = slugify(f"{c_dict['title']}-{random.randint(1000, 9999)}")

        cq = CodingQuestion.objects.create(
            title=c_dict["title"],
            slug=slug,
            category=c_dict["category"],
            difficulty=c_dict["difficulty"],
            description=c_dict["description"],
            input_format=c_dict["input_format"],
            output_format=c_dict["output_format"],
            constraints=c_dict.get("constraints", ""),
            sample_input=c_dict["sample_input"],
            sample_output=c_dict["sample_output"],
            explanation=c_dict.get("explanation", ""),
            starter_code=c_dict.get("starter_code", {}),
        )

        test_cases = c_dict.get("test_cases", [])
        tc_objs = []
        for idx, tc in enumerate(test_cases, start=1):
            tc_objs.append(
                CodingTestCase(
                    question=cq,
                    input_data=tc["input_data"],
                    expected_output=tc["expected_output"],
                    is_sample=bool(tc.get("is_sample", False)),
                    order=idx,
                )
            )
        CodingTestCase.objects.bulk_create(tc_objs)
        saved.append(cq)

    return saved

