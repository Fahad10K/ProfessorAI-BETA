"""
Quiz Service - Handles MCQ quiz generation and evaluation for ProfAI
"""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from services.llm_service import LLMService
from models.schemas import Quiz, QuizQuestion, QuizSubmission, QuizResult, QuizDisplay, QuizQuestionDisplay
import config

class QuizService:
    """Service for generating and evaluating MCQ quizzes."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.quiz_storage_dir = os.path.join(os.path.dirname(__file__), "..", "data", "quizzes")
        self.answers_storage_dir = os.path.join(os.path.dirname(__file__), "..", "data", "quiz_answers")
        
        # Ensure storage directories exist
        os.makedirs(self.quiz_storage_dir, exist_ok=True)
        os.makedirs(self.answers_storage_dir, exist_ok=True)
        
        # Initialize database service (use DatabaseServiceV2)
        try:
            from services.database_service_v2 import DatabaseServiceV2
            self.db_service = DatabaseServiceV2()
            logging.info("QuizService initialized with DatabaseServiceV2 support")
        except Exception as e:
            logging.warning(f"Database service not available: {e}")
            self.db_service = None
            logging.info("QuizService initialized (JSON mode)")
    
    async def generate_module_quiz(self, module_week: int, course_content: dict) -> Quiz:
        """Generate a 20-question MCQ quiz for a specific module."""
        try:
            # Find the specific module
            module = None
            for mod in course_content.get("modules", []):
                if mod.get("week") == module_week:
                    module = mod
                    break
            
            if not module:
                raise ValueError(f"Module week {module_week} not found in course content")
            
            # Extract content for the module
            module_content = self._extract_module_content(module)
            
            # Generate quiz using LLM
            quiz_id = f"module_{module_week}_{uuid.uuid4().hex[:8]}"
            
            logging.info(f"Generating 20-question quiz for module week {module_week}")
            
            quiz_prompt = self._create_module_quiz_prompt(module, module_content)
            quiz_response = await self.llm_service.generate_response(quiz_prompt, temperature=1.0)
            
            # Parse the LLM response into structured quiz
            questions = self._parse_quiz_response(quiz_response, quiz_id)
            
            # Ensure we have exactly 20 questions
            if len(questions) < 20:
                # Generate additional questions if needed
                additional_prompt = self._create_additional_questions_prompt(module_content, 20 - len(questions))
                additional_response = await self.llm_service.generate_response(additional_prompt, temperature=1.0)
                additional_questions = self._parse_quiz_response(additional_response, quiz_id, start_id=len(questions))
                questions.extend(additional_questions)
            
            # Take only first 20 questions
            questions = questions[:20]
            
            quiz = Quiz(
                quiz_id=quiz_id,
                title=f"Module {module_week} Quiz: {module.get('title', 'Module Quiz')}",
                description=f"20-question MCQ quiz covering content from Week {module_week}",
                questions=questions,
                total_questions=len(questions),
                quiz_type="module",
                module_week=module_week
            )
            
            # Store quiz and answers with course_id (try 'id' then 'course_id')
            cid = course_content.get('id') or course_content.get('course_id')
            self._store_quiz(quiz, cid)
            
            logging.info(f"Generated module quiz with {len(questions)} questions")
            return quiz
            
        except Exception as e:
            logging.error(f"Error generating module quiz: {e}")
            raise e
    
    async def generate_course_quiz(self, course_content: dict) -> Quiz:
        """Generate a 40-question MCQ quiz covering the entire course."""
        try:
            # Extract content from all modules
            all_content = self._extract_all_course_content(course_content)
            
            quiz_id = f"course_{uuid.uuid4().hex[:8]}"
            
            logging.info("Generating 40-question course quiz")
            
            # Generate quiz using LLM in chunks (20 questions at a time for better results)
            quiz_prompt_1 = self._create_course_quiz_prompt(all_content, part=1)
            logging.info("Sending part 1 quiz prompt to LLM...")
            quiz_response_1 = await self.llm_service.generate_response(quiz_prompt_1, temperature=1.0)
            logging.info(f"LLM Response Part 1 (first 500 chars): {quiz_response_1[:500]}")
            questions_1 = self._parse_quiz_response(quiz_response_1, quiz_id, start_id=0)
            logging.info(f"Parsed {len(questions_1)} questions from part 1")
            
            quiz_prompt_2 = self._create_course_quiz_prompt(all_content, part=2)
            logging.info("Sending part 2 quiz prompt to LLM...")
            quiz_response_2 = await self.llm_service.generate_response(quiz_prompt_2, temperature=1.0)
            logging.info(f"LLM Response Part 2 (first 500 chars): {quiz_response_2[:500]}")
            questions_2 = self._parse_quiz_response(quiz_response_2, quiz_id, start_id=20)
            logging.info(f"Parsed {len(questions_2)} questions from part 2")
            
            # Combine all questions
            all_questions = questions_1 + questions_2
            
            # Take exactly 40 questions
            all_questions = all_questions[:40]
            
            quiz = Quiz(
                quiz_id=quiz_id,
                title=f"Final Course Quiz: {course_content.get('course_title', 'Course Quiz')}",
                description="40-question comprehensive MCQ quiz covering the entire course content",
                questions=all_questions,
                total_questions=len(all_questions),
                quiz_type="course",
                module_week=None
            )
            
            # Store quiz and answers with course_id (try 'id' then 'course_id')
            cid = course_content.get('id') or course_content.get('course_id')
            self._store_quiz(quiz, cid)
            
            logging.info(f"Generated course quiz with {len(all_questions)} questions")
            return quiz
            
        except Exception as e:
            logging.error(f"Error generating course quiz: {e}")
            raise e
    
    def evaluate_quiz(self, submission: QuizSubmission) -> QuizResult:
        """Evaluate a quiz submission and return results."""
        try:
            # Try to load quiz from database first
            quiz_data = None
            correct_answers = {}
            
            if self.db_service:
                try:
                    db_quiz = self.db_service.get_quiz(submission.quiz_id)
                    if db_quiz and db_quiz.get('questions'):
                        # Extract correct answers from DB quiz questions
                        for q in db_quiz['questions']:
                            correct_answers[q['question_id']] = q['correct_answer']
                        quiz_data = {
                            'answers': correct_answers,
                            'quiz': {
                                'title': db_quiz.get('title', 'Quiz'),
                                'total_questions': len(db_quiz['questions']),
                                'quiz_type': db_quiz.get('quiz_type', 'module')
                            }
                        }
                        logging.info(f"✅ Loaded quiz {submission.quiz_id} from database for evaluation")
                except Exception as e:
                    logging.warning(f"Failed to load quiz from database: {e}")
            
            # Fallback to JSON files
            if not quiz_data:
                quiz_data = self._load_quiz_answers(submission.quiz_id)
                if quiz_data:
                    correct_answers = quiz_data["answers"]
                    logging.info(f"✅ Loaded quiz {submission.quiz_id} from JSON for evaluation")
            
            if not quiz_data:
                raise ValueError(f"Quiz {submission.quiz_id} not found")
            
            quiz_info = quiz_data["quiz"]
            
            # Calculate score
            score = 0
            detailed_results = []
            
            for question_id, user_answer in submission.answers.items():
                is_correct = user_answer.upper() == correct_answers.get(question_id, "").upper()
                if is_correct:
                    score += 1
                
                detailed_results.append({
                    "question_id": question_id,
                    "user_answer": user_answer.upper(),
                    "correct_answer": correct_answers.get(question_id, ""),
                    "is_correct": is_correct
                })
            
            total_questions = len(correct_answers)
            percentage = (score / total_questions) * 100 if total_questions > 0 else 0
            passed = percentage >= 60.0
            
            result = QuizResult(
                quiz_id=submission.quiz_id,
                user_id=submission.user_id,
                score=score,
                total_questions=total_questions,
                percentage=round(percentage, 2),
                passed=passed,
                detailed_results=detailed_results
            )
            
            # Store submission result
            self._store_submission_result(submission, result)
            
            logging.info(f"Evaluated quiz {submission.quiz_id}: {score}/{total_questions} ({percentage:.1f}%)")
            return result
            
        except Exception as e:
            logging.error(f"Error evaluating quiz: {e}")
            raise e
    
    def get_quiz_without_answers(self, quiz_id: str) -> Optional[QuizDisplay]:
        """Get quiz for display (without correct answers) - tries database first, then JSON."""
        try:
            quiz_data = None
            
            # Try database first
            if self.db_service:
                try:
                    quiz_data = self.db_service.get_quiz(quiz_id)
                    if quiz_data:
                        logging.info(f"✅ Loaded quiz {quiz_id} from database")
                except Exception as e:
                    logging.warning(f"Failed to load quiz from database, trying JSON fallback: {e}")
            
            # Fallback to JSON file
            if not quiz_data:
                quiz_file = os.path.join(self.quiz_storage_dir, f"{quiz_id}.json")
                if not os.path.exists(quiz_file):
                    return None
                
                with open(quiz_file, 'r', encoding='utf-8') as f:
                    quiz_data = json.load(f)
                logging.info(f"✅ Loaded quiz {quiz_id} from JSON file")
            
            # Create display questions without correct answers
            display_questions = []
            for question in quiz_data["questions"]:
                display_question = QuizQuestionDisplay(
                    question_id=question.get("question_id", f"{quiz_id}_q{question.get('question_number', 1)}"),
                    question_text=question.get("question_text", question.get("question", "")),
                    options=question["options"],
                    topic=question.get("topic", "")
                )
                display_questions.append(display_question)
            
            # Create display quiz
            display_quiz = QuizDisplay(
                quiz_id=quiz_data["quiz_id"],
                title=quiz_data["title"],
                description=quiz_data.get("description", ""),
                questions=display_questions,
                total_questions=len(display_questions),
                quiz_type=quiz_data.get("quiz_type", "module"),
                module_week=quiz_data.get("module_week"),
                course_id=str(quiz_data.get("course_id")) if quiz_data.get("course_id") is not None else None
            )
            
            return display_quiz
            
        except Exception as e:
            logging.error(f"Error loading quiz {quiz_id}: {e}")
            return None
    
    def _extract_module_content(self, module: dict) -> str:
        """Extract text content from a module."""
        content_parts = [f"Module Week {module.get('week')}: {module.get('title', '')}"]
        
        for sub_topic in module.get("sub_topics", []):
            content_parts.append(f"\n--- {sub_topic.get('title', '')} ---")
            content_parts.append(sub_topic.get('content', ''))
        
        return "\n".join(content_parts)
    
    def _extract_all_course_content(self, course_content: dict) -> str:
        """Extract text content from entire course."""
        content_parts = [f"Course: {course_content.get('course_title', '')}"]
        
        for module in course_content.get("modules", []):
            content_parts.append(self._extract_module_content(module))
        
        return "\n".join(content_parts)
    
    def _create_module_quiz_prompt(self, module: dict, content: str) -> str:
        """Create prompt for module quiz generation."""
        return f"""Generate a 20-question multiple choice quiz based on the following module content.

MODULE INFORMATION:
Week: {module.get('week')}
Title: {module.get('title', '')}

CONTENT:
{content}

REQUIREMENTS:
1. Generate exactly 20 multiple choice questions
2. Each question should have 4 options (A, B, C, D)
3. Questions should cover different aspects of the module content
4. Mix difficulty levels: 40% easy, 40% medium, 20% hard
5. Include practical application questions
6. Ensure questions test understanding, not just memorization

FORMAT YOUR RESPONSE AS:
Q1. [Question text]
A) [Option A]
B) [Option B] 
C) [Option C]
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]

Q2. [Next question...]

Continue this format for all 20 questions."""
    
    def _create_course_quiz_prompt(self, content: str, part: int) -> str:
        """Create prompt for course quiz generation."""
        question_range = f"questions {1 + (part-1)*20} to {part*20}" if part == 1 else f"questions 21 to 40"
        
        return f"""Generate {question_range} of a comprehensive multiple choice quiz based on the entire course content below.

COURSE CONTENT:
{content[:8000]}  # Limit content to avoid token limits

REQUIREMENTS:
1. Generate exactly 20 multiple choice questions for this part
2. Each question should have 4 options (A, B, C, D)
3. Cover content from all modules proportionally
4. Mix difficulty levels: 30% easy, 50% medium, 20% hard
5. Include synthesis questions that connect concepts across modules
6. Test both theoretical understanding and practical application

FORMAT YOUR RESPONSE AS:
Q{1 + (part-1)*20}. [Question text]
A) [Option A]
B) [Option B]
C) [Option C] 
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]

Continue this format for all 20 questions in this part."""
    
    def _create_additional_questions_prompt(self, content: str, num_questions: int) -> str:
        """Create prompt for generating additional questions."""
        return f"""Generate {num_questions} additional multiple choice questions based on the following content:

{content}

REQUIREMENTS:
1. Generate exactly {num_questions} questions
2. Each question should have 4 options (A, B, C, D)
3. Focus on different aspects not covered in previous questions
4. Maintain good difficulty distribution

FORMAT YOUR RESPONSE AS:
Q. [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]"""
    
    def _parse_quiz_response(self, response: str, quiz_id: str, start_id: int = 0) -> List[QuizQuestion]:
        """Parse LLM response into structured quiz questions."""
        questions = []
        lines = response.split('\n')
        
        logging.info(f"Parsing quiz response with {len(lines)} lines, starting from question {start_id}")
        
        current_question = {}
        question_count = start_id
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Question line - more flexible matching
            if line.startswith('Q') and ('.' in line or ')' in line):
                if current_question and 'question_text' in current_question:
                    # Save previous question
                    question_obj = self._create_question_object(current_question, quiz_id, question_count)
                    if question_obj:
                        questions.append(question_obj)
                    question_count += 1
                
                # Start new question
                current_question = {}
                # Extract question text after Q1., Q2., etc.
                if '.' in line:
                    parts = line.split('.', 1)
                    question_text = parts[1].strip() if len(parts) > 1 else line
                elif ')' in line:
                    parts = line.split(')', 1)
                    question_text = parts[1].strip() if len(parts) > 1 else line
                else:
                    question_text = line
                
                current_question['question_text'] = question_text
                current_question['options'] = []
                logging.debug(f"Found question: {question_text[:50]}...")
            
            # Option lines - handle both A) and A.
            elif line.startswith(('A)', 'B)', 'C)', 'D)', 'A.', 'B.', 'C.', 'D.')):
                if 'options' in current_question:
                    # Remove prefix (A), A., etc)
                    option_text = line[2:].strip() if line[1] in '.)' else line[1:].strip()
                    current_question['options'].append(option_text)
                    logging.debug(f"Added option: {option_text[:30]}...")
            
            # Answer line - handle variations
            elif 'ANSWER:' in line.upper() or 'CORRECT ANSWER:' in line.upper():
                # Extract just the letter
                answer_part = line.split(':', 1)[1].strip() if ':' in line else line
                # Get first letter that's A, B, C, or D
                for char in answer_part.upper():
                    if char in 'ABCD':
                        current_question['correct_answer'] = char
                        logging.debug(f"Set correct answer: {char}")
                        break
            
            # Explanation line
            elif 'EXPLANATION:' in line.upper():
                explanation = line.split(':', 1)[1].strip() if ':' in line else line
                current_question['explanation'] = explanation
        
        # Don't forget the last question
        if current_question and 'question_text' in current_question:
            question_obj = self._create_question_object(current_question, quiz_id, question_count)
            if question_obj:
                questions.append(question_obj)
        
        logging.info(f"Parser extracted {len(questions)} questions from response")
        
        if len(questions) == 0:
            logging.error("⚠️ Parser failed to extract any questions!")
            logging.error(f"Response preview: {response[:1000]}")
        
        return questions
    
    def _create_question_object(self, question_data: dict, quiz_id: str, question_num: int) -> QuizQuestion:
        """Create a QuizQuestion object from parsed data."""
        # Validate we have minimum required data
        if not question_data.get('question_text'):
            logging.warning(f"Question {question_num + 1} missing question_text")
            return None
        
        if len(question_data.get('options', [])) < 4:
            logging.warning(f"Question {question_num + 1} has only {len(question_data.get('options', []))} options")
            # Pad with empty options if needed
            while len(question_data.get('options', [])) < 4:
                question_data.setdefault('options', []).append("Option not provided")
        
        return QuizQuestion(
            question_id=f"{quiz_id}_q{question_num + 1}",
            question_number=question_num + 1,  # Sequential: 1, 2, 3, 4...
            question_text=question_data.get('question_text', ''),
            options=question_data.get('options', [])[:4],  # Ensure max 4 options
            correct_answer=question_data.get('correct_answer', 'A'),
            explanation=question_data.get('explanation', 'No explanation provided'),
            topic=question_data.get('topic', '')
        )
    
    def _store_quiz(self, quiz: Quiz, course_id: str = None):
        """Store quiz - use database if enabled, else JSON files."""
        try:
            # Try database first (if enabled and course_id provided)
            if self.db_service and course_id:
                try:
                    quiz_data = {
                        'quiz_id': quiz.quiz_id,
                        'title': quiz.title,
                        'description': quiz.description,
                        'quiz_type': quiz.quiz_type,
                        'module_week': quiz.module_week,
                        'questions': [q.dict() for q in quiz.questions]
                    }
                    self.db_service.create_quiz(quiz_data, course_id)  # TEXT UUID
                    logging.info(f"✅ Quiz {quiz.quiz_id} saved to database (course: {course_id})")
                    return  # Success - exit early
                except Exception as e:
                    logging.warning(f"Failed to save quiz to database, using JSON fallback: {e}")
            
            # Fallback to JSON files (original logic)
            # Store full quiz data with course_id
            quiz_data = quiz.dict()
            if course_id:
                quiz_data['course_id'] = str(course_id)
            
            quiz_file = os.path.join(self.quiz_storage_dir, f"{quiz.quiz_id}.json")
            with open(quiz_file, 'w', encoding='utf-8') as f:
                json.dump(quiz_data, f, indent=2, ensure_ascii=False)
            
            # Store answers separately for evaluation
            answers = {}
            for question in quiz.questions:
                answers[question.question_id] = question.correct_answer
            
            answer_data = {
                "quiz_id": quiz.quiz_id,
                "answers": answers,
                "quiz": {
                    "title": quiz.title,
                    "total_questions": quiz.total_questions,
                    "quiz_type": quiz.quiz_type,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            answer_file = os.path.join(self.answers_storage_dir, f"{quiz.quiz_id}_answers.json")
            with open(answer_file, 'w', encoding='utf-8') as f:
                json.dump(answer_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"✅ Quiz {quiz.quiz_id} saved to JSON files")
            
        except Exception as e:
            logging.error(f"Error storing quiz: {e}")
            raise e
    
    def _load_quiz_answers(self, quiz_id: str) -> Optional[dict]:
        """Load quiz answers for evaluation."""
        try:
            answer_file = os.path.join(self.answers_storage_dir, f"{quiz_id}_answers.json")
            if not os.path.exists(answer_file):
                return None
            
            with open(answer_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logging.error(f"Error loading quiz answers: {e}")
            return None
    
    def _store_submission_result(self, submission: QuizSubmission, result: QuizResult):
        """Store quiz submission and result - database first, then JSON fallback."""
        try:
            # Try database first (if enabled)
            if self.db_service:
                try:
                    response_data = {
                        'quiz_id': submission.quiz_id,
                        'user_id': submission.user_id,
                        'answers': submission.answers,  # Dict to JSONB
                        'score': result.score,
                        'total_questions': result.total_questions,
                        'correct_answers': result.score,  # Same as score
                        'time_taken': None  # Can add later if needed
                    }
                    self.db_service.save_quiz_response(response_data)
                    logging.info(f"✅ Quiz response saved to database for user {submission.user_id}")
                    return  # Success - exit early
                except Exception as e:
                    logging.warning(f"Failed to save quiz response to database, using JSON fallback: {e}")
            
            # Fallback to JSON files (original logic)
            submission_data = {
                "submission": submission.dict(),
                "result": result.dict(),
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            submission_file = os.path.join(
                self.answers_storage_dir, 
                f"{submission.quiz_id}_{submission.user_id}_submission.json"
            )
            
            with open(submission_file, 'w', encoding='utf-8') as f:
                json.dump(submission_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Stored submission result to JSON for user {submission.user_id}")
            
        except Exception as e:
            logging.error(f"Error storing submission result: {e}")
