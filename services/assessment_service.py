"""
Assessment Service - Handles assessment generation from user-uploaded notes
Generates MCQ assessments similar to quiz_service but from user documents
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from services.llm_service import LLMService
from services.document_extractor import DocumentExtractor
from services.database_service_v2 import DatabaseServiceV2

logger = logging.getLogger(__name__)

class AssessmentService:
    """Service for generating and evaluating assessments from uploaded notes"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.doc_extractor = DocumentExtractor()
        self.db_service = DatabaseServiceV2()
        logger.info("AssessmentService initialized with DatabaseServiceV2")
    
    async def process_and_generate_assessment(
        self,
        user_id: int,
        session_id: int,
        file_bytes_list: List[Tuple[bytes, str, str]],  # [(bytes, filename, filetype), ...]
        difficulty_level: str = 'medium',
        num_questions: int = 20
    ) -> Optional[Dict]:
        """
        Process uploaded documents and generate assessment
        
        Args:
            user_id: User ID
            session_id: Session ID
            file_bytes_list: List of tuples (file_bytes, file_name, file_type)
            difficulty_level: Difficulty level (easy, medium, hard)
            num_questions: Number of questions to generate
            
        Returns:
            Assessment data with questions (without answers)
        """
        try:
            if len(file_bytes_list) > 3:
                raise ValueError("Maximum 3 documents allowed")
            
            # Extract content from all documents
            all_content = []
            uploaded_note_ids = []
            
            for file_bytes, file_name, file_type in file_bytes_list:
                # Extract content
                content = self.doc_extractor.extract_from_bytes(file_bytes, file_name, file_type)
                
                if not content:
                    logger.warning(f"Failed to extract content from {file_name}")
                    continue
                
                all_content.append(f"--- Document: {file_name} ---\n{content}")
                
                # Store in database
                note_id = self.db_service.create_uploaded_note(
                    user_id=user_id,
                    session_id=session_id,
                    file_name=file_name,
                    file_type=file_type,
                    file_size=len(file_bytes),
                    content=content
                )
                
                if note_id:
                    uploaded_note_ids.append(note_id)
                    logger.info(f"✅ Stored note {note_id} from {file_name}")
            
            if not all_content:
                raise ValueError("No content could be extracted from the uploaded documents")
            
            # Combine all content
            combined_content = "\n\n".join(all_content)
            
            # Generate assessment using LLM
            logger.info(f"Generating {num_questions}-question assessment for user {user_id}")
            
            assessment_prompt = self._create_assessment_prompt(
                combined_content, 
                num_questions, 
                difficulty_level
            )
            
            llm_response = await self.llm_service.generate_response(
                assessment_prompt, 
                temperature=0.8
            )
            
            # Parse questions
            questions = self._parse_assessment_response(llm_response)
            
            # Ensure we have the requested number of questions
            if len(questions) < num_questions:
                logger.warning(f"Only generated {len(questions)}/{num_questions} questions")
            
            questions = questions[:num_questions]
            
            # Create assessment in database (use first uploaded note ID)
            assessment_id = self.db_service.create_assessment(
                user_id=user_id,
                session_id=session_id,
                uploaded_note_id=uploaded_note_ids[0],
                title=f"Assessment from {file_bytes_list[0][1]}" + (f" and {len(file_bytes_list)-1} more" if len(file_bytes_list) > 1 else ""),
                description=f"{num_questions}-question assessment generated from uploaded notes",
                difficulty_level=difficulty_level,
                total_questions=len(questions)
            )
            
            if not assessment_id:
                raise Exception("Failed to create assessment in database")
            
            # Store questions in database
            for idx, question_data in enumerate(questions, 1):
                self.db_service.create_assessment_question(
                    assessment_id=assessment_id,
                    question_number=idx,
                    question_text=question_data['question_text'],
                    options=question_data['options'],
                    correct_answer=question_data['correct_answer'],
                    explanation=question_data.get('explanation'),
                    difficulty=difficulty_level,
                    points=1
                )
            
            logger.info(f"✅ Created assessment {assessment_id} with {len(questions)} questions")
            
            # Return assessment without correct answers
            return self._format_assessment_for_display(assessment_id, questions)
            
        except Exception as e:
            logger.error(f"Error processing and generating assessment: {e}")
            raise
    
    async def submit_assessment(
        self,
        user_id: int,
        session_id: int,
        assessment_id: int,
        answers: Dict[str, str],  # {question_number: selected_answer}
        time_taken: int = None
    ) -> Dict:
        """
        Submit assessment answers and calculate score
        
        Args:
            user_id: User ID
            session_id: Session ID
            assessment_id: Assessment ID
            answers: User's answers {question_number: answer}
            time_taken: Time taken in seconds
            
        Returns:
            Evaluation results with score and feedback
        """
        try:
            # Get assessment questions with correct answers
            questions = self.db_service.get_assessment_questions(assessment_id)
            
            if not questions:
                raise ValueError(f"Assessment {assessment_id} not found")
            
            # Evaluate answers
            score = 0
            correct_answers = 0
            incorrect_answers = 0
            detailed_results = []
            
            for question in questions:
                q_num = str(question['question_number'])
                user_answer = answers.get(q_num, '').upper()
                correct_answer = question['correct_answer'].upper()
                
                is_correct = user_answer == correct_answer
                
                if is_correct:
                    score += question.get('points', 1)
                    correct_answers += 1
                else:
                    incorrect_answers += 1
                
                detailed_results.append({
                    'question_number': question['question_number'],
                    'question_text': question['question_text'],
                    'user_answer': user_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct,
                    'explanation': question.get('explanation', '')
                })
            
            total_questions = len(questions)
            percentage = (score / total_questions * 100) if total_questions > 0 else 0
            
            # Save response to database
            response_id = self.db_service.save_assessment_response(
                user_id=user_id,
                session_id=session_id,
                assessment_id=assessment_id,
                answers=answers,
                score=score,
                percentage=percentage,
                total_questions=total_questions,
                correct_answers=correct_answers,
                incorrect_answers=incorrect_answers,
                time_taken=time_taken
            )
            
            logger.info(f"✅ Evaluated assessment {assessment_id}: {score}/{total_questions} ({percentage:.1f}%)")
            
            return {
                'response_id': response_id,
                'assessment_id': assessment_id,
                'user_id': user_id,
                'score': score,
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'percentage': round(percentage, 2),
                'passed': percentage >= 60.0,
                'time_taken': time_taken,
                'detailed_results': detailed_results
            }
            
        except Exception as e:
            logger.error(f"Error submitting assessment: {e}")
            raise
    
    def get_assessment_for_display(self, assessment_id: int) -> Optional[Dict]:
        """Get assessment without correct answers for display"""
        try:
            assessment = self.db_service.get_assessment(assessment_id)
            
            if not assessment:
                return None
            
            questions = self.db_service.get_assessment_questions(assessment_id)
            
            # Format questions without correct answers
            display_questions = []
            for q in questions:
                display_questions.append({
                    'question_number': q['question_number'],
                    'question_text': q['question_text'],
                    'options': q['options'],
                    'difficulty': q.get('difficulty', 'medium')
                })
            
            return {
                'assessment_id': assessment_id,
                'title': assessment['title'],
                'description': assessment['description'],
                'difficulty_level': assessment['difficulty_level'],
                'total_questions': assessment['total_questions'],
                'passing_score': assessment.get('passing_score', 60),
                'time_limit': assessment.get('time_limit'),
                'questions': display_questions
            }
            
        except Exception as e:
            logger.error(f"Error getting assessment for display: {e}")
            return None
    
    def get_user_assessments(self, user_id: int) -> List[Dict]:
        """Get all assessments for a user"""
        try:
            return self.db_service.get_user_assessments(user_id)
        except Exception as e:
            logger.error(f"Error getting user assessments: {e}")
            return []
    
    def get_assessment_attempts(self, user_id: int, assessment_id: int) -> List[Dict]:
        """Get user's attempts for an assessment"""
        try:
            return self.db_service.get_user_assessment_responses(user_id, assessment_id)
        except Exception as e:
            logger.error(f"Error getting assessment attempts: {e}")
            return []
    
    def _create_assessment_prompt(self, content: str, num_questions: int, difficulty: str) -> str:
        """Create prompt for LLM to generate assessment questions"""
        
        difficulty_guidance = {
            'easy': 'Focus on basic recall and understanding. Questions should test fundamental concepts.',
            'medium': 'Mix recall with application. Questions should require understanding and basic application.',
            'hard': 'Focus on analysis and synthesis. Questions should require deep understanding and critical thinking.'
        }
        
        return f"""Generate a {num_questions}-question multiple choice assessment based on the following content.

CONTENT:
{content[:12000]}  # Limit to avoid token limits

DIFFICULTY LEVEL: {difficulty.upper()}
{difficulty_guidance.get(difficulty, '')}

REQUIREMENTS:
1. Generate exactly {num_questions} multiple choice questions
2. Each question must have exactly 4 options (A, B, C, D)
3. Questions should thoroughly cover the key concepts in the content
4. Ensure questions test understanding, not just memorization
5. Questions should be clear, unambiguous, and have one correct answer
6. Include the explanation for why the correct answer is right

FORMAT YOUR RESPONSE EXACTLY AS SHOWN:
Q1. [Question text here]
A) [Option A text]
B) [Option B text]
C) [Option C text]
D) [Option D text]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation of why this is correct]

Q2. [Next question...]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
ANSWER: [A/B/C/D]
EXPLANATION: [Brief explanation]

Continue this exact format for all {num_questions} questions.
IMPORTANT: Do not deviate from this format. Each question must be numbered Q1, Q2, etc."""
    
    def _parse_assessment_response(self, llm_response: str) -> List[Dict]:
        """Parse LLM response into structured questions"""
        questions = []
        
        # Split by question numbers
        question_blocks = re.split(r'\n(?=Q\d+\.)', llm_response)
        
        for block in question_blocks:
            if not block.strip():
                continue
            
            try:
                # Extract question text
                question_match = re.search(r'Q\d+\.\s*(.+?)(?=\n[A-D]\))', block, re.DOTALL)
                if not question_match:
                    continue
                
                question_text = question_match.group(1).strip()
                
                # Extract options
                options = {}
                for option in ['A', 'B', 'C', 'D']:
                    option_pattern = rf'{option}\)\s*(.+?)(?=\n[A-D]\)|ANSWER:|$)'
                    option_match = re.search(option_pattern, block, re.DOTALL)
                    if option_match:
                        options[option] = option_match.group(1).strip()
                
                # Skip if we don't have all 4 options
                if len(options) != 4:
                    logger.warning(f"Skipping question with incomplete options: {question_text[:50]}...")
                    continue
                
                # Extract answer
                answer_match = re.search(r'ANSWER:\s*([A-D])', block, re.IGNORECASE)
                if not answer_match:
                    logger.warning(f"Skipping question without answer: {question_text[:50]}...")
                    continue
                
                correct_answer = answer_match.group(1).upper()
                
                # Extract explanation (optional)
                explanation = ""
                explanation_match = re.search(r'EXPLANATION:\s*(.+?)(?=\n\n|Q\d+\.|$)', block, re.DOTALL)
                if explanation_match:
                    explanation = explanation_match.group(1).strip()
                
                questions.append({
                    'question_text': question_text,
                    'options': options,
                    'correct_answer': correct_answer,
                    'explanation': explanation
                })
                
            except Exception as e:
                logger.warning(f"Error parsing question block: {e}")
                continue
        
        logger.info(f"Parsed {len(questions)} questions from LLM response")
        return questions
    
    def _format_assessment_for_display(self, assessment_id: int, questions: List[Dict]) -> Dict:
        """Format assessment for display (without correct answers)"""
        display_questions = []
        
        for idx, q in enumerate(questions, 1):
            display_questions.append({
                'question_number': idx,
                'question_text': q['question_text'],
                'options': q['options']
            })
        
        return {
            'assessment_id': assessment_id,
            'total_questions': len(questions),
            'questions': display_questions
        }
