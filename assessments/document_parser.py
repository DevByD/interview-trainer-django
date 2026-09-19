"""Document parsing and question extraction service for Assessment Creation.

Supports PDF, DOCX, and TXT files.
Extracts questions, MCQ options, correct answers, explanations, and coding challenges.
Strictly preserves question content without AI modifications or external questions.
"""

import io
import os
import re
from typing import Any, BinaryIO, Union

from assessments.models import AssessmentDocument, Question


ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_document_file(file_obj: Any) -> tuple[bool, str, str, int]:
    """Validate uploaded file format and size.

    Returns:
        (is_valid, error_message, file_extension, file_size)
    """
    if not file_obj or not hasattr(file_obj, "name"):
        return False, "No file was selected for upload.", "", 0

    filename = os.path.basename(file_obj.name)
    parts = filename.rsplit(".", 1)
    if len(parts) < 2:
        return False, "File must have an extension (.pdf, .docx, or .txt).", "", 0

    ext = parts[1].lower().strip()
    if ext not in ALLOWED_EXTENSIONS:
        return (
            False,
            f"Unsupported file format '.{ext}'. Supported formats: PDF, DOCX, TXT.",
            ext,
            0,
        )

    content_type = getattr(file_obj, "content_type", "").lower()
    dangerous_content_types = {
        "application/x-msdownload",
        "application/x-dosexec",
        "application/x-executable",
        "application/x-sh",
        "application/x-bat",
        "application/x-csh",
    }
    if content_type in dangerous_content_types:
        return False, "Executable files are not permitted.", ext, 0

    # Check for executable binary headers (e.g. Windows PE 'MZ' header)
    try:
        current_pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
        header_bytes = file_obj.read(4) if hasattr(file_obj, "read") else b""
        if hasattr(file_obj, "seek"):
            file_obj.seek(current_pos)
        if header_bytes.startswith(b"MZ"):
            return False, "Executable binary files are not permitted.", ext, 0
    except Exception:
        pass

    file_size = getattr(file_obj, "size", 0)
    if file_size <= 0:
        # Attempt to read length if size not directly populated
        try:
            current_pos = file_obj.tell()
            file_obj.seek(0, os.SEEK_END)
            file_size = file_obj.tell()
            file_obj.seek(current_pos)
        except Exception:
            file_size = 0

    if file_size <= 0:
        return False, "The uploaded file is empty.", ext, 0

    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        return (
            False,
            f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed size of {max_mb} MB.",
            ext,
            file_size,
        )

    return True, "", ext, file_size


def extract_text_from_file(file_input: Union[str, BinaryIO, Any], file_type: str) -> str:
    """Extract full raw text from PDF, DOCX, or TXT file."""
    file_type = file_type.lower().strip()

    if file_type == "txt":
        # Handle file-like object or path
        if hasattr(file_input, "read"):
            content_bytes = file_input.read()
            if hasattr(file_input, "seek"):
                file_input.seek(0)
        else:
            with open(file_input, "rb") as f:
                content_bytes = f.read()

        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content_bytes.decode("utf-8", errors="replace")

    elif file_type == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("pypdf is required to process PDF files.")

        reader = PdfReader(file_input)
        pages_text = []
        for page in reader.pages:
            pt = page.extract_text() or ""
            if pt.strip():
                pages_text.append(pt)
        if hasattr(file_input, "seek"):
            file_input.seek(0)
        return "\n\n".join(pages_text)

    elif file_type == "docx":
        try:
            import docx
        except ImportError:
            raise RuntimeError("python-docx is required to process DOCX files.")

        # Ensure file pointer is at start
        if hasattr(file_input, "seek"):
            file_input.seek(0)

        # docx.Document accepts a file path or file-like stream
        if not isinstance(file_input, (str, os.PathLike)) and hasattr(file_input, "read"):
            stream = io.BytesIO(file_input.read())
            doc = docx.Document(stream)
            if hasattr(file_input, "seek"):
                file_input.seek(0)
        else:
            doc = docx.Document(file_input)

        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also process any tables containing questions
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    lines.append(" | ".join(row_cells))
        return "\n".join(lines)

    else:
        raise ValueError(f"Unsupported file format: {file_type}")


def parse_questions_from_text(raw_text: str) -> list[dict]:
    """Parse raw text from document into structured question dictionaries.

    Supports:
    - Various question numbering formats (1., 1), 1 -, Q1., Q1:, Question 1:, etc.)
    - Option labels (A., A), (A), [A], A -, a., etc.)
    - Inline options (A. ... B. ... C. ... D. ...)
    - Inline answers and standalone Answer Key sections at the end of documents
    - Multi-line question text and explanations
    - Section headers (LOGICAL, QUANTITATIVE, TECHNICAL)
    - Coding questions if detected
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # 1. Parse standalone Answer Key at document end if present
    answer_key_map: dict[int, str] = {}
    main_lines = []
    in_answer_key = False

    answer_key_header_re = re.compile(
        r"^\s*(?:answer\s*key|answers\s*:?|answer\s*sheet|solution\s*key|answer\s*table)\b",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if answer_key_header_re.match(stripped):
            in_answer_key = True
            continue
        if in_answer_key:
            # Matches: 1. A, 1: A, Q1: A, 1-A, 1) B, 1 -> C, etc.
            matches = re.findall(
                r"(?:Q\.?\s*)?(\d+)[\s.:=\->]+(?:\(?[Option\s]*\)?)*\s*\(?([A-Da-d])\)?",
                line,
            )
            for q_num, ans in matches:
                try:
                    answer_key_map[int(q_num)] = ans.upper()
                except ValueError:
                    pass
        else:
            main_lines.append(line)

    # 2. Regex Patterns
    # Question start: "1. What is...", "1) What is...", "1 - What is...", "Q1. ...", "Question 1: ..."
    q_start_re = re.compile(
        r"^\s*(?:(?:Question|Problem|Coding\s+Question|Q\.?)\s*(\d+)[:.)\s\-]*|(\d+)(?:\s*[-:]|[\.\)]))\s*(.*)",
        re.IGNORECASE,
    )

    # Single option start: "A. ...", "A) ...", "(A) ...", "[A] ...", "A - ...", "A: ..."
    opt_start_re = re.compile(
        r"^\s*(?:\(([A-Da-d])\)|\[([A-Da-d])\]|([A-Da-d])(?:\s*[-:]|[\.\)]))\s+(.*)"
    )

    # Inline options pattern: line containing multiple option letters
    inline_opts_re = re.compile(
        r"(?:\(([A-Da-d])\)|\[([A-Da-d])\]|\b([A-Da-d])(?:\s*[-:]|[\.\)]))\s+(.*?)(?=\([A-Da-d]\)|\[[A-Da-d]\]|\b[A-Da-d](?:\s*[-:]|[\.\)])|$)"
    )

    # Answer line pattern: "Answer: A", "Ans: (B)", "Correct: C", "Correct Answer: D", "Key: D", "Answer: Option A"
    ans_line_re = re.compile(
        r"^\s*(?:Correct\s+Answer|Correct\s+Option|Correct|Answer|Ans|Key)\s*[:=\-]?\s*(?:Option\s*)?\(?([A-Da-d])\)?(?:\.|\:)?\s*(.*)",
        re.IGNORECASE,
    )

    # Explanation line pattern: "Explanation: ...", "Explain: ..."
    exp_line_re = re.compile(
        r"^\s*(?:Explanation|Explain|Reason)\s*[:=\-]?\s*(.*)",
        re.IGNORECASE,
    )

    # Section header detection: "Section: Logical Reasoning", "Category: Technical"
    section_header_re = re.compile(
        r"^\s*(?:Section|Category|Part)\s*[:=\-]?\s*(Logical|Quantitative|Technical|Coding|Aptitude)",
        re.IGNORECASE,
    )

    current_section = Question.Sections.TECHNICAL
    questions: list[dict] = []
    current_q: dict | None = None
    current_opt: str | None = None

    def finalize_current_q():
        nonlocal current_q
        if not current_q:
            return

        current_q["question_text"] = current_q["question_text"].strip()
        q_num = current_q.get("number")

        # If answer was not in question body, check answer key map
        if not current_q.get("correct_answer") and q_num in answer_key_map:
            current_q["correct_answer"] = answer_key_map[q_num]
            current_q["has_answer"] = True

        has_options = bool(current_q.get("option_a") or current_q.get("option_b"))
        is_explicit_coding = "coding" in current_q.get("raw_header", "").lower()
        has_coding_keywords = (
            "write a function" in current_q["question_text"].lower()
            or "write a program" in current_q["question_text"].lower()
            or "input format" in current_q["question_text"].lower()
        )

        if is_explicit_coding or (not has_options and has_coding_keywords):
            current_q["type"] = "CODING"
            lines_q = current_q["question_text"].split("\n")
            current_q["title"] = lines_q[0][:100].strip() or f"Coding Challenge {q_num}"
            current_q["description"] = current_q["question_text"]
            current_q["input_format"] = "Standard Input"
            current_q["output_format"] = "Standard Output"
            current_q["sample_input"] = ""
            current_q["sample_output"] = ""
            current_q["has_answer"] = True  # Coding questions don't require MCQ correct_answer
        else:
            current_q["type"] = "MCQ"
            current_q["option_a"] = current_q.get("option_a", "").strip()[:255]
            current_q["option_b"] = current_q.get("option_b", "").strip()[:255]
            current_q["option_c"] = current_q.get("option_c", "").strip()[:255]
            current_q["option_d"] = current_q.get("option_d", "").strip()[:255]

            # If binary choice (e.g. True/False), fill empty C and D with "N/A"
            if not current_q["option_c"] and not current_q["option_d"] and current_q["option_a"] and current_q["option_b"]:
                current_q["option_c"] = "N/A"
                current_q["option_d"] = "N/A"

            ans = current_q.get("correct_answer", "").strip().upper()
            if ans in ("A", "B", "C", "D"):
                current_q["correct_answer"] = ans
                current_q["has_answer"] = True
            else:
                current_q["correct_answer"] = ""
                current_q["has_answer"] = False

            current_q["options"] = [
                {"label": "A", "text": current_q["option_a"]},
                {"label": "B", "text": current_q["option_b"]},
                {"label": "C", "text": current_q["option_c"]},
                {"label": "D", "text": current_q["option_d"]},
            ]

        if current_q["question_text"]:
            questions.append(current_q)
        current_q = None

    for line in main_lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Check section header
        sec_m = section_header_re.match(trimmed)
        if sec_m:
            sec_val = sec_m.group(1).upper()
            if "LOGIC" in sec_val:
                current_section = Question.Sections.LOGICAL
            elif "QUANT" in sec_val:
                current_section = Question.Sections.QUANTITATIVE
            else:
                current_section = Question.Sections.TECHNICAL
            continue

        # Check question start
        q_m = q_start_re.match(trimmed)
        if q_m:
            finalize_current_q()
            num_str = q_m.group(1) or q_m.group(2)
            q_num = int(num_str) if num_str and num_str.isdigit() else (len(questions) + 1)
            rest_of_text = q_m.group(3)
            current_q = {
                "number": q_num,
                "question_num": q_num,
                "raw_header": trimmed[:30],
                "question_text": rest_of_text,
                "section": current_section,
                "category": "Document Extracted",
                "difficulty": Question.Difficulties.MEDIUM,
                "option_a": "",
                "option_b": "",
                "option_c": "",
                "option_d": "",
                "correct_answer": "",
                "has_answer": False,
                "explanation": "",
            }
            current_opt = None
            continue

        if not current_q:
            # Preamble or header before first question
            continue

        # Check answer line
        ans_m = ans_line_re.match(trimmed)
        if ans_m:
            ans_letter = ans_m.group(1).upper()
            current_q["correct_answer"] = ans_letter
            current_q["has_answer"] = True
            extra_exp = ans_m.group(2).strip()
            if extra_exp and not current_q["explanation"]:
                current_q["explanation"] = extra_exp
            current_opt = None
            continue

        # Check explanation line
        exp_m = exp_line_re.match(trimmed)
        if exp_m:
            current_q["explanation"] = exp_m.group(1).strip()
            current_opt = None
            continue

        # Check inline options: line contains at least 2 option letters
        inline_matches = inline_opts_re.findall(trimmed)
        if len(inline_matches) >= 2:
            for m in inline_matches:
                opt_letter = (m[0] or m[1] or m[2]).upper()
                opt_text = m[3].strip()
                if opt_letter in ("A", "B", "C", "D"):
                    current_q[f"option_{opt_letter.lower()}"] = opt_text
            current_opt = None
            continue

        # Check single option start
        opt_m = opt_start_re.match(trimmed)
        if opt_m:
            opt_letter = (opt_m.group(1) or opt_m.group(2) or opt_m.group(3)).upper()
            opt_text = opt_m.group(4).strip()
            if opt_letter in ("A", "B", "C", "D"):
                current_opt = f"option_{opt_letter.lower()}"
                current_q[current_opt] = opt_text
            continue

        # If we are currently reading an option, continuation line
        if current_opt:
            current_q[current_opt] += " " + trimmed
        else:
            # Continuation line of question text
            current_q["question_text"] += "\n" + trimmed

    finalize_current_q()
    return questions


def process_uploaded_document(doc_instance: AssessmentDocument) -> tuple[bool, str, list[dict]]:
    """Extract text from AssessmentDocument, parse questions, update document status.

    Returns:
        (success, error_message, list_of_parsed_questions)
    """
    try:
        raw_text = extract_text_from_file(doc_instance.file.path, doc_instance.file_type)
    except Exception as exc:
        doc_instance.status = AssessmentDocument.Status.FAILED
        doc_instance.error_message = f"Failed to extract text from file: {exc}"
        doc_instance.save(update_fields=["status", "error_message", "updated_at"])
        return False, doc_instance.error_message, []

    if not raw_text or not raw_text.strip():
        doc_instance.status = AssessmentDocument.Status.FAILED
        doc_instance.error_message = "No readable text could be extracted from the uploaded document."
        doc_instance.save(update_fields=["status", "error_message", "updated_at"])
        return False, doc_instance.error_message, []

    doc_instance.raw_text = raw_text

    try:
        parsed_questions = parse_questions_from_text(raw_text)
    except Exception as exc:
        doc_instance.status = AssessmentDocument.Status.FAILED
        doc_instance.error_message = f"Error during question parsing: {exc}"
        doc_instance.save(update_fields=["status", "error_message", "raw_text", "updated_at"])
        return False, doc_instance.error_message, []

    if not parsed_questions:
        doc_instance.status = AssessmentDocument.Status.FAILED
        doc_instance.error_message = (
            "No questions could be recognized in the uploaded document. "
            "Please ensure the document contains numbered questions and MCQ options (A, B, C, D)."
        )
        doc_instance.save(update_fields=["status", "error_message", "raw_text", "updated_at"])
        return False, doc_instance.error_message, []

    doc_instance.status = AssessmentDocument.Status.PROCESSED
    doc_instance.extracted_count = len(parsed_questions)
    doc_instance.error_message = ""
    doc_instance.save(update_fields=["status", "extracted_count", "error_message", "raw_text", "updated_at"])

    return True, "", parsed_questions
